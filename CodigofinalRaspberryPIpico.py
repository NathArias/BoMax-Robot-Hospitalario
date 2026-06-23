# CASO3FINAL - PROGRAMA COMPLETO PICO CON MANIOBRA DE ULTRASÓNICO
from machine import UART, Pin, PWM, I2C
import time

uart = UART(0, baudrate=9600, tx=Pin(0), rx=Pin(1))

# --- AÑADIDO: CONFIGURACIÓN DEL SENSOR ULTRASÓNICO ---
trig = Pin(28, Pin.OUT)
echo = Pin(27, Pin.IN)

# --- CONFIGURACIÓN DE MOTORES ---
m1_in1 = Pin(10, Pin.OUT)
m1_in2 = Pin(11, Pin.OUT)
m1_pwm = PWM(Pin(12))
m1_pwm.freq(1000)

m2_in1 = Pin(13, Pin.OUT)
m2_in2 = Pin(14, Pin.OUT)
m2_pwm = PWM(Pin(15))
m2_pwm.freq(1000)

VELOCIDAD = 47000

VELOCIDAD_GIRO_MPU_BASE = 47000
VELOCIDAD_GIRO_BUSQUEDA_BASE = 39000
INCREMENTO_GIRO = 7000

habitacion_actual = 1
total_habitaciones = 1
ruta_habitaciones = [1]
indice_ruta = 0

PWM_BASE_DER = 51000
PWM_BASE_IZQ = 48000
PWM_MIN = 20000
PWM_MAX = 60000

Kp_yaw = 500
CORRECCION_MAX = 2000
CONTROL_ACTIVO = False

i2c = I2C(0, scl=Pin(5), sda=Pin(4), freq=400000)
MPU_ADDR = 0x68
i2c.writeto_mem(MPU_ADDR, 0x6B, b'\x00')

yaw = 0
yaw_objetivo = 0
offset_gz = 0
last_time_mpu = time.ticks_ms()

def velocidad_giro_mpu_actual():
    if habitacion_actual == 3:
        return 53000
    return VELOCIDAD_GIRO_MPU_BASE + ((habitacion_actual - 1) * INCREMENTO_GIRO)

def velocidad_giro_busqueda_actual():
    if habitacion_actual == 3:
        return 53000
    return VELOCIDAD_GIRO_BUSQUEDA_BASE + ((habitacion_actual - 1) * INCREMENTO_GIRO)

def angulo_90_actual():
    if habitacion_actual in (2, 3):
        return 81
    return 80

def angulo_180_actual():
    if habitacion_actual in (2, 3):
        return 175
    return 170

def tiempo_avance_tras_rojo_actual():
    if habitacion_actual == 1:
        return 5000
    elif habitacion_actual == 2:
        return 13000
    elif habitacion_actual == 3:
        return 16000
    return 5000

def leer_word(reg):
    high = i2c.readfrom_mem(MPU_ADDR, reg, 1)[0]
    low = i2c.readfrom_mem(MPU_ADDR, reg + 1, 1)[0]
    valor = (high << 8) | low
    if valor >= 32768:
        valor -= 65536
    return valor

def leer_gyro_z():
    return leer_word(0x47) / 131.0

def calibrar_mpu():
    global offset_gz
    print("Calibrando MPU6050...")
    suma = 0
    for i in range(300):
        suma += leer_gyro_z()
        time.sleep(0.01)
    offset_gz = suma / 300
    print("Offset Gyro Z:", offset_gz)

def limitar_pwm(valor):
    if valor < PWM_MIN:
        return PWM_MIN
    if valor > PWM_MAX:
        return PWM_MAX
    return int(valor)

def actualizar_control_mpu():
    global yaw, last_time_mpu

    tiempo_actual = time.ticks_ms()
    dt = time.ticks_diff(tiempo_actual, last_time_mpu) / 1000
    last_time_mpu = tiempo_actual

    gz = leer_gyro_z() - offset_gz
    yaw += gz * dt

    error_yaw = yaw_objetivo - yaw
    correccion = Kp_yaw * error_yaw

    if correccion > CORRECCION_MAX:
        correccion = CORRECCION_MAX
    elif correccion < -CORRECCION_MAX:
        correccion = -CORRECCION_MAX

    m1_pwm.duty_u16(limitar_pwm(PWM_BASE_DER - correccion))
    m2_pwm.duty_u16(limitar_pwm(PWM_BASE_IZQ + correccion))

def detener():
    global CONTROL_ACTIVO
    CONTROL_ACTIVO = False
    m1_pwm.duty_u16(0)
    m2_pwm.duty_u16(0)
    m1_in1.value(0)
    m1_in2.value(0)
    m2_in1.value(0)
    m2_in2.value(0)

def adelante():
    global CONTROL_ACTIVO, yaw, yaw_objetivo, last_time_mpu
    yaw = 0
    yaw_objetivo = 0
    last_time_mpu = time.ticks_ms()
    CONTROL_ACTIVO = True

    m1_in1.value(0)
    m1_in2.value(1)
    m2_in1.value(0)
    m2_in2.value(1)

    m1_pwm.duty_u16(PWM_BASE_DER)
    m2_pwm.duty_u16(PWM_BASE_IZQ)

# --- AÑADIDO: SENTIDO DE MARCHA ATRÁS REGULADO POR MPU ---
def atras():
    global CONTROL_ACTIVO, yaw, yaw_objetivo, last_time_mpu
    yaw = 0
    yaw_objetivo = 0  # Fuerza al robot a ir recto también hacia atrás
    last_time_mpu = time.ticks_ms()
    CONTROL_ACTIVO = True

    m1_in1.value(1)
    m1_in2.value(0)
    m2_in1.value(1)
    m2_in2.value(0)

    m1_pwm.duty_u16(PWM_BASE_DER)
    m2_pwm.duty_u16(PWM_BASE_IZQ)

def avanzar_con_mpu():
    detener()
    time.sleep(0.2)
    adelante()

def derecha(velocidad=VELOCIDAD):
    global CONTROL_ACTIVO
    CONTROL_ACTIVO = False

    m1_in1.value(0)
    m1_in2.value(1)
    m2_in1.value(1)
    m2_in2.value(0)

    m1_pwm.duty_u16(limitar_pwm(velocidad))
    m2_pwm.duty_u16(limitar_pwm(velocidad))

def izquierda(velocidad=VELOCIDAD):
    global CONTROL_ACTIVO
    CONTROL_ACTIVO = False

    m1_in1.value(1)
    m1_in2.value(0)
    m2_in1.value(0)
    m2_in2.value(1)

    m1_pwm.duty_u16(limitar_pwm(velocidad))
    m2_pwm.duty_u16(limitar_pwm(velocidad))

def derecha_lenta():
    derecha(velocidad_giro_mpu_actual())

def izquierda_lenta():
    izquierda(velocidad_giro_mpu_actual())

def girar_90_mpu(direccion):
    global yaw, last_time_mpu

    yaw = 0
    last_time_mpu = time.ticks_ms()

    if direccion == "derecha":
        derecha_lenta()
    else:
        izquierda_lenta()

    while abs(yaw) < angulo_90_actual():
        tiempo_actual = time.ticks_ms()
        dt = time.ticks_diff(tiempo_actual, last_time_mpu) / 1000
        last_time_mpu = tiempo_actual

        gz = leer_gyro_z() - offset_gz
        yaw += gz * dt

        time.sleep(0.005)

    detener()
    time.sleep(0.3)

def girar_180_mpu(direccion):
    global yaw, last_time_mpu

    yaw = 0
    last_time_mpu = time.ticks_ms()

    if direccion == "derecha":
        derecha_lenta()
    else:
        izquierda_lenta()

    while abs(yaw) < angulo_180_actual():
        tiempo_actual = time.ticks_ms()
        dt = time.ticks_diff(tiempo_actual, last_time_mpu) / 1000
        last_time_mpu = tiempo_actual

        gz = leer_gyro_z() - offset_gz
        yaw += gz * dt

        time.sleep(0.005)

    detener()
    time.sleep(0.3)

# --- AÑADIDO: FUNCIÓN DE LECTURA DE DISTANCIA ---
def medir_distancia():
    trig.value(0)
    time.sleep_us(5)
    trig.value(1)
    time.sleep_us(10)
    trig.value(0)
    
    duracion = machine.time_pulse_us(echo, 1, 30000)
    if duracion < 0:
        return 999.0
    return (duracion * 0.0343) / 2

servo = PWM(Pin(2))
servo.freq(50)

angulo_servo = 90
angulo_objetivo_servo = 90
last_time_servo = time.ticks_ms()
VELOCIDAD_SERVO_MS = 15

extremo_servo_alineacion = 90
contador_uno_alineacion = 0

def mover_servo_hardware(angulo):
    if angulo < 0:
        angulo = 0
    if angulo > 180:
        angulo = 180

    duty = int(1638 + (angulo / 180) * 6553)
    servo.duty_u16(duty)

def mover_servo_bloqueante(destino):
    global angulo_servo, angulo_objetivo_servo

    angulo_objetivo_servo = destino

    while angulo_servo != destino:
        if angulo_servo < destino:
            angulo_servo += 1
        elif angulo_servo > destino:
            angulo_servo -= 1

        mover_servo_hardware(angulo_servo)
        time.sleep_ms(VELOCIDAD_SERVO_MS)

    time.sleep(0.3)

def enviar_uart(dato):
    uart.write((dato + "\n").encode())
    print("Enviado a RPi4:", dato)

def limpiar_uart():
    while uart.any():
        uart.readline()

def configurar_ruta_desde_comando(comando):
    global ruta_habitaciones, total_habitaciones, habitacion_actual

    if comando.startswith("I") and len(comando) > 1:
        ruta_habitaciones = []

        for c in comando[1:]:
            if c in ["1", "2", "3"]:
                ruta_habitaciones.append(int(c))

        if len(ruta_habitaciones) == 0:
            ruta_habitaciones = [1]
    else:
        ruta_habitaciones = [1]

    total_habitaciones = len(ruta_habitaciones)
    habitacion_actual = ruta_habitaciones[0]

    print("Ruta recibida:", ruta_habitaciones)
    print("Total habitaciones:", total_habitaciones)
    print("Habitacion actual:", habitacion_actual)

TIEMPO_AVANCE_INICIAL = 3000
TIEMPO_AVANCE_BUSQUEDA = 2000
TIEMPO_AVANCE_1 = 4000
TIEMPO_AVANCE_2 = 4000

estado_general = "ESPERANDO_I"
sub_estado_pausa = "IDLE"      # <-- AÑADIDO: Subestado para la secuencia del ultrasónico

modo_busqueda = False
estado_busqueda = "idle"

tiempo_inicio = 0
tiempo_estado = 0
tiempo_sub_estado = 0          # <-- AÑADIDO: Registro de tiempo para marcha atrás y entrega

direccion_servo = 1

direccion_giro_1 = "derecha"
direccion_giro_180 = "derecha"

def iniciar_entrega_desde_extremo():
    global estado_general, tiempo_estado
    global direccion_giro_1, direccion_giro_180
    global contador_uno_alineacion

    detener()
    contador_uno_alineacion = 0

    mover_servo_bloqueante(90)