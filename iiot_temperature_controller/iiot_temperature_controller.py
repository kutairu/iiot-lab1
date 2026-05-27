"""
@file        main.py
@author      Елисеев Никита Ильич ВТ-1-24
@version     1.0
@date        27.05.2026
@brief       Программа управления вентиляцией по данным датчика DHT22 на MicroPython
@details
* Устройство: ESP32 / Arduino
* Датчик: DHT22 (пин 2)
* Реле: пин 9
* Протокол: MQTT
* Брокер: broker.example.com:1883
*
* Функциональность:
* - Опрос датчика каждые 2 секунды
* - Включение вентиляции при T &gt; 30°C
* - Выключение при T &lt; 25°C
* - Отправка MQTT каждые 10 секунд
* - Буферизация при потере связи
*
* Компетенции: ПК 4.1, ОК 01, ОК 02
"""

import machine
import time
import dht
import ujson
from umqtt.simple import MQTTClient

# Конфигурация пинов и сети
DHT_PIN = 2
RELAY_PIN = 9
WIFI_SSID = "your_SSID"
WIFI_PASSWORD = "your_PASSWORD"
MQTT_SERVER = "broker.example.com"
MQTT_PORT = 1883
MQTT_TOPIC = b"sensors/workshop_1/temperature"

# Инициализация железа
sensor = dht.DHT22(machine.Pin(DHT_PIN))
relay = machine.Pin(RELAY_PIN, machine.Pin.OUT)
relay.value(0)  # Выключаем реле при старте

# Буфер для данных (в Python это делается простым списком)
data_buffer = []

# Подключение к Wi-Fi
def setup_wifi():
    import network
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Connecting to WiFi...")
        wlan.connect(WIFI_SSID, WIFI_PASSWORD)
        while not wlan.isconnected():
            time.sleep(0.5)
            print(".", end="")
    print("\nWiFi connected:", wlan.ifconfig())

# Подключение к MQTT
def setup_mqtt():
    client = MQTTClient("ESP32_Industrial_Client", MQTT_SERVER, port=MQTT_PORT)
    try:
        client.connect()
        print("MQTT connected")
        return client
    except Exception as e:
        print("MQTT connection failed:", e)
        return None

# Логика управления вентиляцией
def control_ventilation(temp):
    if temp > 30.0:
        relay.value(1)  # Включить реле (замыкание)
        print("Ventilation ON")
    elif temp < 25.0:
        relay.value(0)  # Выключить реле (размыкание)
        print("Ventilation OFF")

# Главный запуск
setup_wifi()
mqtt_client = setup_mqtt()

# Таймеры (запоминаем время в миллисекундах)
last_sensor_read = time.ticks_ms()
last_mqtt_send = time.ticks_ms()

print("Starting main loop...")

while True:
    now = time.ticks_ms()

    # 1. Опрос датчика (каждые 2 секунды)
    if time.ticks_diff(now, last_sensor_read) >= 2000:
        try:
            sensor.measure()
            current_temp = sensor.temperature()
            current_hum = sensor.humidity()
            
            control_ventilation(current_temp)
        except Exception as e:
            print("DHT22 read error!", e)
            
        last_sensor_read = now

    # 2. Отправка данных по MQTT (каждые 10 секунд)
    if time.ticks_diff(now, last_mqtt_send) >= 10000:
        # Формируем JSON-сообщение
        payload = {
            "device_id": "1",
            "temp": current_temp if 'current_temp' in locals() else 0.0,
            "hum": current_hum if 'current_hum' in locals() else 0.0
        }
        json_string = ujson.dumps(payload)

        # Проверяем подключение к MQTT
        if mqtt_client is not None:
            try:
                # Отправляем текущее сообщение
                mqtt_client.publish(MQTT_TOPIC, json_string.encode())
                print("MQTT sent:", json_string)

                # Если в буфере есть старые данные, отправляем их по очереди (FIFO)
                while len(data_buffer) > 0:
                    buffered_msg = data_buffer.pop(0)  # Берем самое старое
                    mqtt_client.publish(MQTT_TOPIC, buffered_msg.encode())
                    print("MQTT sent from buffer:", buffered_msg)
            except Exception as e:
                print("Failed to send, reconnecting...", e)
                mqtt_client = setup_mqtt()
        else:
            # Если связи нет, кладем в буфер (максимум 100 записей)
            if len(data_buffer) < 100:
                data_buffer.append(json_string)
                print("MQTT disconnected, data buffered. Buffer size:", len(data_buffer))
            else:
                print("Buffer overflow, data lost")
                
        last_mqtt_send = now

    # Небольшая задержка, чтобы не перегружать процессор
    time.sleep(0.1)