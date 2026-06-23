#!/usr/bin/env python3
import cv2
import numpy as np
import serial
import threading
import time
import ssl
import random
import pigpio
import paho.mqtt.client as mqtt

# ============================================================
# UART A RASPBERRY PI PICO
# ============================================================

try:
    ser = serial.Serial('/dev/serial0', 9600, timeout=0.1)
    print("--- RPi 4 conectada con Pico ---")
except Exception as e:
    print("Error al abrir Serial:", e)
    exit()

ultimo_comando = ""

def enviar_comando(comando):
    global ultimo_comando
    try:
        ser.write((comando + "\n").encode())

        if comando != ultimo_comando:
            print("Comando enviado:", comando)
            ultimo_comando = comando

    except Exception as e:
        print("Error enviando UART:", e)

def leer_uart():
    try:
        if ser.in_waiting > 0:
            dato = ser.readline().decode(errors="ignore").strip().upper()

            if dato:
                print("Comando recibido Pico:", dato)
                return dato

    except Exception as e:
        print("Error leyendo UART:", e)

    return None

# ============================================================
# SERVOS / DISPENSACIÓN
# ============================================================

MQTT_SERVER = "29d811ffe864444aa0fe55f7224f194c.s1.eu.hivemq.cloud"
MQTT_PORT = 8883
MQTT_USER = "bomax_user"
MQTT_PASS = "BoMax2026!Robot"

MQTT_TOPIC_ESTADO = "bomax/dispenser/estado"

PIN_S1 = 12
PIN_S2 = 13
PIN_S3 = 16
PIN_S4 = 18
PIN_S5 = 19
PIN_S6 = 20
PIN_S7 = 21
PIN_S8 = 22
PIN_S9 = 23

pi = pigpio.pi()
client = None
servo_pos = {}

S1_HOME, S1_DROP = 180, 140
S2_MID, S2_OPEN = 60, 180
S3_MID, S3_OPEN = 90, 20

S4_HOME, S4_DROP = 180, 0
S5_HOME, S5_ACTIVO = 0, 180
S6_HOME, S6_ACTIVO = 180, 0

S7_POS_A = 95
S7_POS_B = 40

S8_POS_A = 15
S8_POS_B = 120

def deg_to_pw(deg):
    deg = max(0, min(180, deg))
    return int(500 + (deg / 180.0) * 2000)

def move_servo(pin, target, speed=15):
    curr = servo_pos.get(pin, target)

    if curr == target:
        pi.set_servo_pulsewidth(pin, deg_to_pw(target))
        servo_pos[pin] = target
        return

    step = 1 if curr < target else -1

    for p in range(curr, target + step, step):
        pi.set_servo_pulsewidth(pin, deg_to_pw(p))
        time.sleep(speed / 1000.0)

    servo_pos[pin] = target

def move_servos_sync(pin1, target1, pin2, target2, delay_steps=15):
    pos1 = servo_pos.get(pin1, target1)
    pos2 = servo_pos.get(pin2, target2)

    pasos = max(abs(target1 - pos1), abs(target2 - pos2))

    if pasos == 0:
        pi.set_servo_pulsewidth(pin1, deg_to_pw(target1))
        pi.set_servo_pulsewidth(pin2, deg_to_pw(target2))
        servo_pos[pin1] = target1
        servo_pos[pin2] = target2
        return

    for i in range(pasos + 1):
        f1 = i / pasos
        n1 = round(pos1 + (target1 - pos1) * f1)
        pi.set_servo_pulsewidth(pin1, deg_to_pw(n1))

        if i > delay_steps:
            denom = max(1, pasos - delay_steps)
            f2 = (i - delay_steps) / denom
            f2 = min(max(f2, 0), 1)

            n2 = round(pos2 + (target2 - pos2) * f2)
            pi.set_servo_pulsewidth(pin2, deg_to_pw(n2))

        time.sleep(0.02)

    servo_pos[pin1] = target1
    servo_pos[pin2] = target2

def publicar_estado(msg):
    global client

    print("ESTADO:", msg)

    if client and client.is_connected():
        client.publish(MQTT_TOPIC_ESTADO, msg)

def dispensar_h1():
    print("💊 Secuencia H1")
    move_servo(PIN_S1, S1_DROP, 15)
    time.sleep(1.5)
    move_servo(PIN_S1, S1_HOME, 15)
    print("✅ H1 Listo")
    publicar_estado("H1 OK")

def dispensar_h2():
    print("💊 Secuencia H2")
    move_servo(PIN_S2, S2_OPEN, 20)
    time.sleep(0.5)
    move_servo(PIN_S1, S1_DROP, 15)
    time.sleep(2.0)
    move_servo(PIN_S1, S1_HOME, 15)
    move_servo(PIN_S2, S2_MID, 20)
    print("✅ H2 Listo")
    publicar_estado("H2 OK")

def dispensar_h3():
    print("💊 Secuencia H3")
    move_servo(PIN_S3, S3_OPEN, 20)
    time.sleep(0.5)
    move_servo(PIN_S1, S1_DROP, 15)
    time.sleep(2.0)
    move_servo(PIN_S1, S1_HOME, 15)
    move_servo(PIN_S3, S3_MID, 20)
    print("✅ H3 Listo")
    publicar_estado("H3 OK")

def llegada_h1():
    print("📦 Llegada H1")
    move_servo(PIN_S4, S4_DROP, 20)
    time.sleep(1.5)
    move_servo(PIN_S4, S4_HOME, 20)
    publicar_estado("LLEGADA_H1 OK")

def llegada_h2():
    print("📦 Llegada H2")
    move_servo(PIN_S5, S5_ACTIVO, 20)
    time.sleep(1.5)
    move_servo(PIN_S5, S5_HOME, 20)
    publicar_estado("LLEGADA_H2 OK")

def llegada_h3():
    print("📦 Llegada H3")
    move_servo(PIN_S6, S6_ACTIVO, 20)
    time.sleep(1.5)
    move_servo(PIN_S6, S6_HOME, 20)
    publicar_estado("LLEGADA_H3 OK")

def brazo_entregar():
    print("🤖 Brazo entregando")
    move_servo(PIN_S7, 80, speed=10)
    time.sleep(0.2)

    move_servos_sync(
        PIN_S7, S7_POS_B,
        PIN_S8, S8_POS_B
    )

    publicar_estado("ENTREGA COMPLETADA")

def brazo_bajar():
    print("🤖 Brazo bajando")
    move_servos_sync(PIN_S7, S7_POS_A, PIN_S8, S8_POS_A)
    publicar_estado("BRAZO DOWN")

def reset_to_ready():
    print("🔄 Reset servos")

    move_servo(PIN_S1, S1_HOME)
    move_servo(PIN_S2, S2_MID)
    move_servo(PIN_S3, S3_MID)
    move_servo(PIN_S4, S4_HOME)
    move_servo(PIN_S5, S5_HOME)
    move_servo(PIN_S6, S6_HOME)
    move_servos_sync(PIN_S7, S7_POS_A, PIN_S8, S8_POS_A)

    publicar_estado("RESET OK")

def setup_servos():
    if not pi.connected:
        raise RuntimeError("pigpiod no está corriendo. Ejecuta: sudo pigpiod")

    for pin in [PIN_S1, PIN_S2, PIN_S3, PIN_S4, PIN_S5, PIN_S6, PIN_S7, PIN_S8, PIN_S9]:
        pi.set_mode(pin, pigpio.OUTPUT)
        pi.set_servo_pulsewidth(pin, 0)

    iniciales = [
        (PIN_S1, S1_HOME),
        (PIN_S2, S2_MID),
        (PIN_S3, S3_MID),
        (PIN_S4, S4_HOME),
        (PIN_S5, S5_HOME),
        (PIN_S6, S6_HOME),
        (PIN_S7, S7_POS_A),
        (PIN_S8, S8_POS_A),
    ]

    for pin, pos in iniciales:
        servo_pos[pin] = pos
        pi.set_servo_pulsewidth(pin, deg_to_pw(pos))
        time.sleep(0.2)

def conectar_mqtt():
    global client

    try:
        client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"BoMax_{random.randint(1000,9999)}"
        )

        client.username_pw_set(MQTT_USER, MQTT_PASS)
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)

        client.connect(MQTT_SERVER, MQTT_PORT, 60)
        client.loop_start()

        print("MQTT conectado")

    except Exception as e:
        print("MQTT no conectado:", e)
        client = None

def preparar_medicamentos(ruta_letras):
    print("Preparando medicamentos...")

    # Para 1H, SIEMPRE usa H1 aunque se busque cualquier color.
    if len(ruta_letras) == 1:
        dispensar_h1()
        return

    for letra in ruta_letras:
        if letra == "A":
            dispensar_h1()
        elif letra == "B":
            dispensar_h2()
        elif letra == "C":
            dispensar_h3()

def ejecutar_entrega_actual(ruta_letras, indice_actual):
    print("Ejecutando entrega final...")

    # Para 1H, SIEMPRE entrega con H1 aunque el color buscado sea otro.
    if len(ruta_letras) == 1:
        llegada_h1()
        brazo_entregar()
        brazo_bajar()
        return

    letra = ruta_letras[indice_actual]

    if letra == "A":
        llegada_h1()
    elif letra == "B":
        llegada_h2()
    elif letra == "C":
        llegada_h3()

    brazo_entregar()
    brazo_bajar()

# ============================================================
# CÁMARA Y VISIÓN
# ============================================================

cap = None

def iniciar_camara():
    global cap

    if cap is None:
        cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        print("Cámara encendida")

def apagar_camara():
    global cap

    if cap is not None:
        cap.release()
        cap = None
        cv2.destroyAllWindows()
        print("Cámara apagada")

MAPEO_LETRAS = {
    "A": "AMARILLO",
    "B": "AZUL",
    "C": "VERDE"
}

MAPEO_NUMEROS = {
    "A": "1",
    "B": "2",
    "C": "3"
}

COLOR_RANGES = {
    "AZUL": [
        ((80, 100, 40), (110, 255, 255)),
        ((110, 100, 40), (140, 255, 255))
    ],
    "VERDE": [
        ((35, 60, 30), (100, 255, 255))
    ],
    "AMARILLO": [
        ((18, 80, 100), (45, 255, 255))
    ],
    "ROJO": [
        ((0, 175, 100), (10, 255, 255)),
        ((170, 175, 100), (180, 255, 255))
    ]
}

AREA_MINIMA = 2500
DIF_LADOS_MAX = 35
RELACION_MIN = 0.80
RELACION_MAX = 1.20

FRAMES_CONFIRMACION = 3
FRAMES_PERDIDOS_MAX = 10
TOLERANCIA_CENTRO = 60

estado_sistema = "REPOSO"
color_objetivo = ""
orden_colores = []
indice_color = 0

ejecutando = True
camara_activada = False

detecciones_seguidas = 0
frames_perdidos = 0
frames_centrado = 0

ultimo_centro = None
ultimo_rect = None

datos_deteccion = {
    "cx": None,
    "cy": None,
    "rect": None,
    "frame": None
}

lock_datos = threading.Lock()

def comando_inicio_por_ruta(letras_ruta):
    comando = "I"

    for letra in letras_ruta:
        comando += MAPEO_NUMEROS[letra]

    return comando

def detectar_cuadrado_color(frame, color_buscado):
    if color_buscado not in COLOR_RANGES:
        return None, None, None, frame

    blurred = cv2.bilateralFilter(frame, 9, 75, 75)
    hsv = cv2.cvtColor(blurred, cv2.COLOR_BGR2HSV)

    mascara_total = np.zeros(hsv.shape[:2], dtype=np.uint8)

    for bajo, alto in COLOR_RANGES[color_buscado]:
        bajo = np.array(bajo, dtype=np.uint8)
        alto = np.array(alto, dtype=np.uint8)

        mascara = cv2.inRange(hsv, bajo, alto)
        mascara_total = cv2.bitwise_or(mascara_total, mascara)

    kernel = np.ones((5, 5), np.uint8)
    mascara_total = cv2.morphologyEx(mascara_total, cv2.MORPH_OPEN, kernel)
    mascara_total = cv2.morphologyEx(mascara_total, cv2.MORPH_CLOSE, kernel)

    contornos, _ = cv2.findContours(
        mascara_total,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    mejor = None
    mayor_area = 0

    for contorno in contornos:
        area = cv2.contourArea(contorno)

        if area < AREA_MINIMA:
            continue

        perimetro = cv2.arcLength(contorno, True)

        if perimetro == 0:
            continue

        approx = cv2.approxPolyDP(contorno, 0.04 * perimetro, True)

        if (len(approx) == 4 or len(approx) == 5) and cv2.isContourConvex(approx):
            x, y, w, h = cv2.boundingRect(approx)
            relacion = w / float(h)
            diferencia_lados = abs(w - h)
            area_rect = w * h

            if area_rect == 0:
                continue

            llenado = area / area_rect

            if (
                RELACION_MIN <= relacion <= RELACION_MAX and
                diferencia_lados <= DIF_LADOS_MAX and
                llenado >= 0.75
            ):
                if area > mayor_area:
                    mayor_area = area
                    mejor = (x, y, w, h, approx)

    if mejor is not None:
        x, y, w, h, approx = mejor

        cx = x + w // 2
        cy = y + h // 2

        cv2.drawContours(frame, [approx], -1, (0, 255, 0), 3)
        cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 255), 2)
        cv2.circle(frame, (cx, cy), 6, (0, 0, 255), -1)

        cv2.putText(
            frame,
            color_buscado,
            (x, y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )

        return cx, cy, (x, y, w, h), frame

    return None, None, None, frame

def hilo_vision():
    global ejecutando, estado_sistema, color_objetivo
    global cap, datos_deteccion, camara_activada

    while ejecutando:
        if camara_activada:
            if cap is None:
                iniciar_camara()

            ret, frame = cap.read()

            if not ret:
                time.sleep(0.01)
                continue

            if estado_sistema in ["BUSCANDO", "GIRO_1_ROJO"]:
                cx, cy, rect, frame_procesado = detectar_cuadrado_color(
                    frame,
                    color_objetivo
                )
            else:
                cx, cy, rect, frame_procesado = None, None, None, frame

            with lock_datos:
                datos_deteccion = {
                    "cx": cx,
                    "cy": cy,
                    "rect": rect,
                    "frame": frame_procesado
                }

            time.sleep(0.02)

        else:
            time.sleep(0.1)

def reiniciar_deteccion():
    global detecciones_seguidas, frames_perdidos
    global frames_centrado, ultimo_centro, ultimo_rect

    detecciones_seguidas = 0
    frames_perdidos = 0
    frames_centrado = 0
    ultimo_centro = None
    ultimo_rect = None

def configurar_logistica():
    while True:
        print("\n==========================================")
        print("MAPEO FIJO:")
        print("a = AMARILLO")
        print("b = AZUL")
        print("c = VERDE")

        opcion = input("¿Cuántas habitaciones? (1H / 2H / 3H): ").strip().upper()

        if opcion not in ["1H", "2H", "3H"]:
            print("Opción inválida.")
            continue

        if opcion == "1H":
            entrada = input("Ingrese color/habitación a buscar (a / b / c): ").strip().lower()
            entrada = entrada.replace(" ", "")

            if len(entrada) == 1:
                letra = entrada.upper()

                if letra in MAPEO_LETRAS:
                    print("Modo 1H seleccionado.")
                    print("Color a buscar:", MAPEO_LETRAS[letra])
                    print("Servos: SIEMPRE H1.")
                    return [letra], [MAPEO_LETRAS[letra]]

            print("Letra inválida.")

        elif opcion == "2H":
            entrada = input("Ingrese dos habitaciones. Ejemplo: a b, a c, b c: ").strip().lower()
            entrada = entrada.replace(",", " ")
            entrada = entrada.replace("-", " ")
            partes = entrada.split()

            if len(partes) == 2:
                letras = [partes[0].upper(), partes[1].upper()]

                if (
                    letras[0] in MAPEO_LETRAS and
                    letras[1] in MAPEO_LETRAS and
                    letras[0] != letras[1]
                ):
                    return letras, [MAPEO_LETRAS[letras[0]], MAPEO_LETRAS[letras[1]]]

            print("Ruta inválida.")

        elif opcion == "3H":
            letras = ["A", "B", "C"]
            colores = ["AMARILLO", "AZUL", "VERDE"]

            print("Ruta 3H fija seleccionada:")
            print("A → B → C")
            print("AMARILLO → AZUL → VERDE")

            return letras, colores

# ============================================================
# PROGRAMA PRINCIPAL
# ============================================================

if __name__ == "__main__":

    setup_servos()
    conectar_mqtt()

    t_vision = threading.Thread(target=hilo_vision, daemon=True)
    t_vision.start()

    try:
        while True:
            letras_ruta, orden_colores = configurar_logistica()

            indice_color = 0
            color_objetivo = orden_colores[indice_color]

            reiniciar_deteccion()
            estado_sistema = "PREPARANDO"
            camara_activada = False

            print("\nRuta logística guardada:", orden_colores)
            print("Color objetivo inicial:", color_objetivo)

            reset_to_ready()

            preparar_medicamentos(letras_ruta)

            comando_inicio = comando_inicio_por_ruta(letras_ruta)

            estado_sistema = "ESPERANDO_B"

            print("Enviando comando", comando_inicio, "a Pico...")
            enviar_comando(comando_inicio)

            while estado_sistema != "REPOSO":

                dato_uart = leer_uart()

                if dato_uart == "B" and estado_sistema == "ESPERANDO_B":
                    camara_activada = True
                    reiniciar_deteccion()

                    indice_color = 0
                    color_objetivo = orden_colores[indice_color]
                    estado_sistema = "BUSCANDO"

                    print("Buscando habitación/color:", color_objetivo)
                    enviar_comando("2")

                elif dato_uart == "W":
                    indice_color += 1

                    if indice_color < len(orden_colores):
                        camara_activada = True
                        reiniciar_deteccion()

                        color_objetivo = orden_colores[indice_color]
                        estado_sistema = "BUSCANDO"

                        print("Buscando siguiente habitación:", color_objetivo)
                        enviar_comando("2")

                    else:
                        print("W recibido, pero no hay más habitaciones.")

                elif dato_uart in ["U", "LLEGADA", "DISTANCIA_OK"]:
                    print("\nPico se detuvo por ultrasónico a 50 cm.")
                    print("Ejecutando entrega con servos...")

                    camara_activada = False
                    apagar_camara()

                    estado_sistema = "ENTREGANDO"

                    ejecutar_entrega_actual(letras_ruta, indice_color)

                    print("Entrega terminada. Enviando E a Pico.")
                    enviar_comando("E")

                    estado_sistema = "ESPERANDO_RETORNO"

                elif dato_uart == "R1":
                    print("\nPico solicita búsqueda de ROJO para retorno.")

                    camara_activada = True
                    reiniciar_deteccion()

                    color_objetivo = "ROJO"
                    estado_sistema = "GIRO_1_ROJO"

                elif dato_uart == "P":
                    print("\nMisión completada.")
                    estado_sistema = "REPOSO"
                    camara_activada = False
                    apagar_camara()
                    break

                if not camara_activada:
                    time.sleep(0.05)
                    continue

                with lock_datos:
                    cx = datos_deteccion["cx"]
                    cy = datos_deteccion["cy"]
                    rect = datos_deteccion["rect"]
                    frame = datos_deteccion["frame"]

                if frame is None:
                    time.sleep(0.01)
                    continue

                alto, ancho, _ = frame.shape
                centro_x = ancho // 2
                centro_y = alto // 2

                cv2.line(frame, (ancho // 3, 0), (ancho // 3, alto), (255, 0, 0), 1)
                cv2.line(frame, (2 * ancho // 3, 0), (2 * ancho // 3, alto), (255, 0, 0), 1)
                cv2.circle(frame, (centro_x, centro_y), 8, (255, 255, 255), -1)

                if estado_sistema in ["BUSCANDO", "GIRO_1_ROJO"]:

                    if cx is not None:
                        detecciones_seguidas += 1
                        frames_perdidos = 0

                        ultimo_centro = (cx, cy)
                        ultimo_rect = rect

                        error_x = cx - centro_x

                        if detecciones_seguidas >= FRAMES_CONFIRMACION:

                            if abs(error_x) <= TOLERANCIA_CENTRO:
                                frames_centrado += 1
                                enviar_comando("1")

                                if estado_sistema == "GIRO_1_ROJO":
                                    msg = "ROJO CENTRADO - ENVIANDO 1 {}/3".format(frames_centrado)

                                    if frames_centrado >= FRAMES_CONFIRMACION:
                                        print("Rojo confirmado. Pico debe detener giro.")
                                        camara_activada = False
                                        apagar_camara()
                                        estado_sistema = "ESPERANDO_P"

                                else:
                                    msg = "CENTRADO - ENVIANDO 1 {}/3".format(frames_centrado)

                            else:
                                frames_centrado = 0

                                if estado_sistema == "GIRO_1_ROJO":
                                    enviar_comando("2")
                                    msg = "ROJO DETECTADO, ESPERANDO CENTRO..."
                                else:
                                    if error_x < 0:
                                        enviar_comando("4")
                                        msg = "COLOR A LA IZQUIERDA - ENVIANDO 4"
                                    else:
                                        enviar_comando("3")
                                        msg = "COLOR A LA DERECHA - ENVIANDO 3"

                        else:
                            enviar_comando("2")
                            msg = "CONFIRMANDO {} {}/3".format(
                                color_objetivo,
                                detecciones_seguidas
                            )

                        cv2.line(frame, (centro_x, centro_y), (cx, cy), (0, 255, 0), 2)

                    else:
                        frames_perdidos += 1
                        detecciones_seguidas = 0
                        frames_centrado = 0

                        if frames_perdidos > FRAMES_PERDIDOS_MAX:
                            reiniciar_deteccion()

                        enviar_comando("2")

                        if estado_sistema == "GIRO_1_ROJO":
                            msg = "BUSCANDO ROJO..."
                        else:
                            msg = "BUSCANDO COLOR..."

                    cv2.putText(
                        frame,
                        msg,
                        (10, 65),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.7,
                        (0, 255, 0),
                        2
                    )

                cv2.imshow("Vision Robotica RPi4 - BoMax FINAL", frame)

                if cv2.waitKey(1) & 0xFF == ord("q"):
                    estado_sistema = "REPOSO"
                    break

                time.sleep(0.01)

    except KeyboardInterrupt:
        print("\nCierre por teclado.")

    finally:
        ejecutando = False
        camara_activada = False
        apagar_camara()

        try:
            ser.close()
        except:
            pass

        if client:
            client.loop_stop()
            client.disconnect()

        for pin in [PIN_S1, PIN_S2, PIN_S3, PIN_S4, PIN_S5, PIN_S6, PIN_S7, PIN_S8, PIN_S9]:
            pi.set_servo_pulsewidth(pin, 0)

        pi.stop()
