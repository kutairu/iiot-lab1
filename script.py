import time
import random
import json
import sys
from collections import deque
import paho.mqtt.client as mqtt

# ИСПРАВЛЕНО: Правильный порт датчика
SENSOR_PORT = 4  
DHT_INTERVAL = 2.0      # Период опроса датчика (2 секунды)
MQTT_INTERVAL = 10.0    # Период отправки данных (10 секунд)

# Корректные параметры тестового MQTT-брокера
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "sensors/workshop_1/temperature"

# ИСПРАВЛЕНО: Ограниченный кольцевой буфер (макс. 100 записей).
# Защищает от утечек памяти: старые элементы автоматически стираются при переполнении.
MAX_BUFFER_SIZE = 100
data_buffer = deque(maxlen=MAX_BUFFER_SIZE)

current_temp = 0.0
current_hum = 0.0
relay_state = "LOW"

def read_dht_sensor():
    """Эмуляция работы датчика DHT22"""
    if SENSOR_PORT != 4:
        return None, None
    # Генерируем реалистичные промышленные показатели
    t = round(random.uniform(23.0, 33.0), 1)
    h = round(random.uniform(50.0, 65.0), 1)
    return t, h

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("Успешно подключено к MQTT-брокеру!")
    else:
        print(f"Ошибка подключения, код: {rc}")

def main():
    global current_temp, current_hum, relay_state
    
    # ИСПРАВЛЕНО: Инициализация и настройка MQTT-клиента
    client = mqtt.Client()
    client.on_connect = on_connect
    
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start() # Запуск сетевого потока в фоне (вместо ручного loop)
    except Exception as e:
        print(f"Предупреждение: Брокер недоступен ({e}). Переход в автономный режим буферизации.")

    last_sensor_read = time.time()
    last_mqtt_send = time.time()

    print("IIoT Устройство запущено и функционирует...")

    try:
        while True:
            now = time.time()

            # 1. Опрос датчика с правильным тайм-менеджментом
            if now - last_sensor_read >= DHT_INTERVAL:
                temp, hum = read_dht_sensor()
                if temp is not None:
                    current_temp, current_hum = temp, hum
                    print(f"[Датчик] Температура: {current_temp}°C, Влажность: {current_hum}%")
                else:
                    print("[Ошибка] Датчик не обнаружен! Проверьте порт.")
                
                # ИСПРАВЛЕНО: Сброс таймера опроса
                last_sensor_read = now 

            # 2. ИСПРАВЛЕНО: Корректная логика термостата вентиляции
            if current_temp > 30.0:
                if relay_state != "HIGH":
                    relay_state = "HIGH"
                    print("[Реле] Превышение порога! Вентиляция: ВКЛЮЧЕНА (HIGH)")
            elif current_temp < 25.0:
                if relay_state != "LOW":
                    relay_state = "LOW"
                    print("[Реле] Температура в норме. Вентиляция: ВЫКЛЮЧЕНА (LOW)")

            # 3. Периодическая отправка данных и менеджмент буфера
            if now - last_mqtt_send >= MQTT_INTERVAL:
                # Оптимизация: Формирование JSON с помощью f-строк (быстрее и легче)
                json_payload = f'{{"temp": {current_temp}, "hum": {current_hum}, "ventilation": "{relay_state}"}}'
                
                if client.is_connected():
                    # Если сеть восстановилась, сначала выгружаем накопленный буфер (FIFO)
                    while data_buffer:
                        buffered_msg = data_buffer.popleft()
                        client.publish(MQTT_TOPIC, buffered_msg)
                        print(f"[Буфер -> Сеть] Отправлено архивное сообщение: {buffered_msg}")
                    
                    # Отправляем текущую телеметрию
                    client.publish(MQTT_TOPIC, json_payload)
                    print(f"[Сеть] Отправлена текущая телеметрия: {json_payload}")
                else:
                    # ИСПРАВЛЕНО: Безопасное сохранение без утечек памяти
                    if len(data_buffer) >= MAX_BUFFER_SIZE:
                        print("[Буфер] Внимание: Буфер переполнен! Старые данные будут перезаписаны.")
                    data_buffer.append(json_payload)
                    print(f"[Буфер] Нет связи. Данные сохранены локально. В буфере: {len(data_buffer)} записей.")

                # Выполнение индивидуального задания: мониторинг памяти буфера
                # Поскольку deque жестко лимитирован, его размер в байтах не растет бесконечно
                buffer_memory_bytes = sys.getsizeof(data_buffer)
                print(f"[Диагностика] Память под буфер стабильна: {buffer_memory_bytes} байт.\n")
                
                last_mqtt_send = now

            time.sleep(0.1) # Разгружаем процессор

    except KeyboardInterrupt:
        print("\nОстановка IIoT устройства оператором.")
        client.loop_stop()
        client.disconnect()

if __name__ == "__main__":
    main()