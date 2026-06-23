# BoMax - Sistema Robótico Autónomo Hospitalario 
Repositorio de software del proyecto BoMax: HMI en Node-RED, Visión en OpenCV y Control en Raspberry Pi Pico

## Estructura del Repositorio
Este repositorio contiene la lógica distribuida en los tres módulos principales de la arquitectura:
1. **`/Node-RED`**: Contiene el archivo `.json` exportable con la Interfaz Humano-Máquina (HMI), paneles de monitoreo, y lógica de almacenamiento en InfluxDB.
2. **`/Raspberry_Pi_4`**: Scripts en Python para el "Cerebro Estratégico". Maneja la visión artificial (OpenCV) y el cliente MQTT.
3. **`/Raspberry_Pi_Pico`**: Firmware de bajo nivel para el "Cerebro Táctico". Ejecuta el control PID de lazo cerrado, odometría y evasión reactiva de obstáculos.

## ⚙️ Especificaciones de Uso 
Para inicializar el sistema BoMax de manera autónoma e independiente de una computadora central:
1. **Base de Datos y HMI:** Importar el archivo `bomax_flow.json` en Node-RED. Asegurarse de tener el nodo de InfluxDB y configurar las credenciales.
2. **Conexión MQTT en la Nube:** El sistema utiliza un clúster remoto para garantizar independencia local. Utiliza las credenciales SSL hacia `29d811ffe864444aa0fe55f7224f194c.s1.eu.hivemq.cloud` (Puerto `8883`).
3. **Lógica Estratégica (RPi 4):** Ejecutar el script principal de Python: `# CodigoRaspberrypi4.py`.
4. **Control Táctico (Pi Pico):** Ejecutar el script principal de Python: `# CodigofinalRaspberryPIpico.py`. Energizar la placa; el firmware iniciará el control de tracción y quedará a la espera de las coordenadas seriales desde la RPi 4. 

## 🔐 Credenciales de Acceso al Sistema (Norma CFR21 Parte 11)
El sistema HMI de BoMax cuenta con tres niveles de acceso, cada uno con permisos específicos según el rol del usuario dentro del hospital para garantizar la trazabilidad de los datos:

* **Operador (Enfermero/a)**
  * **Usuario:** `enfermera` | **Contraseña:** `1234`
  * **Permisos:** Acceso al tablero principal para crear misiones de entrega, visualizar el mapa en tiempo real, monitorear la posición del robot y registrar las entregas a los pacientes.

* **Supervisor**
  * **Usuario:** `supervisora` | **Contraseña:** `admin2026`
  * **Permisos:** Acceso a la configuración del entorno. Puede cambiar el mapa del hospital (Traumatología, Pediatría o Medicina Interna) para operar, aplicándose automáticamente a todos los operadores.

* **Administrador**
  * **Usuario:** `administrador` | **Contraseña:** `bomax2026`
  * **Permisos:** Acceso completo a la base de datos inalterable. Consulta del historial de misiones, gráficas estadísticas (entregas por día, por enfermero, top medicamentos), filtrado por fechas y exportación a CSV/PDF.

## Guía de Mantenimiento y Solución de Problemas
* **Fallo en la comunicación MQTT (Latencia > 1s):** Verificar la salida a internet de la red Wi-Fi del hospital, ya que el servidor HiveMQ requiere conexión externa por el puerto 8883.
* **Sistema congelado en la HMI:** Si la memoria RAM se satura por exceso de registros, se debe ejecutar el reinicio controlado del flujo y verificar el límite de buffer de entrada.
* **Fallo en el reconocimiento de habitaciones:** Limpiar el lente de la cámara Raspberry Pi v2 y asegurar que la iluminación del pasillo hospitalario no genere reflejos que saturen los umbrales de OpenCV.
* **El robot no se detiene ante obstaculos:** Verificar la conexión física a 5V de los sensores ultrasónicos HC-SR04.
