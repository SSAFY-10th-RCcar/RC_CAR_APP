from Raspi_MotorHAT import Raspi_MotorHAT, Raspi_DCMotor
from Raspi_PWM_Servo_Driver import PWM
import mysql.connector
from threading import Timer, Lock
from time import sleep
import signal
import sys
from sense_hat import SenseHat
from time import sleep
import datetime
import dotenv
import os
import paho.mqtt.client as mqtt

dotenv_file = dotenv.find_dotenv()
dotenv.load_dotenv(dotenv_file)


def closeDB(signal, frame):
    print("BYE")
    mh.getMotor(2).run(Raspi_MotorHAT.RELEASE)
    cur.close()
    db.close()
    timer.cancel()
    timer2.cancel()
    timer3.cancel()
    timer4.cancel()
    sys.exit(0)


def polling():
    global cur, db, ready

    lock.acquire()
    # cur.execute("select * from wasd order by time desc limit 1")
    cur.execute("select * from wasd where id = 1")
    for id, w, a, s, d, is_finish, time in cur:
        # if is_finish == 1 : break
        ready = (w, a, s, d)
        # cur.execute("update wasd set is_finish=1 where is_finish=0")

    db.commit()
    lock.release()

    global timer
    timer = Timer(0.05, polling)
    timer.start()


def sensing():
    global cur, db, sense, velo

    pressure = sense.get_pressure()
    temp = sense.get_temperature()
    humidity = sense.get_humidity()

    accel = sense.get_accelerometer_raw()

    time = datetime.datetime.now()
    num1 = round(pressure / 10000, 3)
    num2 = round(temp / 100, 2)
    num3 = round(humidity / 100, 2)

    acc = round(accel["x"], 3)
    num5 = round(accel["y"], 3)
    num6 = round(accel["z"], 3)
    # print("acc = ", acc, "m/s^2")

    if acc > 0.08:
        velo += acc

    if speed == 0:
        velo = 0

    is_finish = 0
    print("x=", acc, ", y=", num5, ", z=", num6)
    print("acc = ", acc, ", velo = ", velo, "m/s")
    query = "UPDATE sensing SET time = %s, pressure = %s, temp = %s, humid = %s, velo = %s, is_finish = %s WHERE id = 1"
    value = (time, num1, num2, num3, round(velo, 3), is_finish)
    lock.acquire()
    cur.execute(query, value)
    db.commit()
    lock.release()

    global timer2
    timer2 = Timer(1, sensing)
    timer2.start()


def DC():
    global W, S, speed
    lock.acquire()
    #
    if W == 1:  # 가속
        if speed < 200:
            speed += 20
    elif S == 1:  # 감속
        if speed > -200:
            speed -= 20
    else:  # 0으로
        if speed > 0:
            speed -= 20
        elif speed < 0:
            speed += 20

    if speed > 0:
        myMotor.setSpeed(speed)
        myMotor.run(Raspi_MotorHAT.BACKWARD)
    elif speed < 0:
        myMotor.setSpeed(-speed)
        myMotor.run(Raspi_MotorHAT.FORWARD)
    elif speed == 0:
        myMotor.run(Raspi_MotorHAT.RELEASE)

    lock.release()

    global timer3
    timer3 = Timer(0.05, DC)
    timer3.start()


def servo():
    global A, D
    lock.acquire()

    if A == 1:  # Left
        pwm.setPWM(0, 0, 250)
    elif D == 1:  # Right
        pwm.setPWM(0, 0, 420)
    else:  # Middle
        pwm.setPWM(0, 0, 355)
    lock.release()

    global timer4
    timer4 = Timer(0.05, servo)
    timer4.start()


# def on_message(client, userdata, message):
#     global X, Y
#     command = message.payload.decode()
#     X, Y = command.split()
#     X = round(X)
#     Y = round(Y)
#     print("X=", X, ", Y=", Y)


def mqtt_subscriber(broker_address, topic):
    client = mqtt.Client()

    def on_connect(client, userdata, flags, rc):
        print("Connected with result code " + str(rc))
        client.subscribe(topic)

    def on_message(client, userdata, message):
        global X, Y
        command = message.payload.decode()
        X, Y = map(float, command.split())
        print("X=", X, ", Y=", Y)
        if 95 <= X <= 155:
            X = 125

    client.on_message = on_message
    client.on_connect = on_connect

    client.connect(broker_address, 1883, 60)
    client.loop_start()  # 별도 스레드에서 loop_forever() 실행

    # while True:
    #     sleep(0.05)
    # global timer
    # timer = Timer(0.05, lambda: client.loop_stop())
    # timer.start()


def DC_phone():
    global Y
    lock.acquire()

    if Y < 125:  # 전진
        myMotor.setSpeed(250)
        myMotor.run(Raspi_MotorHAT.BACKWARD)
    elif Y > 125:  # 후진
        myMotor.setSpeed(250)
        myMotor.run(Raspi_MotorHAT.FORWARD)
    elif Y == 125:
        myMotor.run(Raspi_MotorHAT.RELEASE)

    lock.release()

    global timer3
    timer3 = Timer(0.05, DC_phone)
    timer3.start()


def servo_phone():
    global X
    lock.acquire()

    if X < 125:  # Left
        pwm.setPWM(0, 0, 250)
    elif X > 125:  # Right
        pwm.setPWM(0, 0, 420)
    elif X == 125:  # Middle
        pwm.setPWM(0, 0, 355)

    lock.release()

    global timer3
    timer4 = Timer(0.05, servo_phone)
    timer4.start()


# Main
if __name__ == "__main__":
    # init
    db = mysql.connector.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_SCHEMA"],
        auth_plugin=os.environ["AUTH_PLUGIN"],
    )

    # DB data receive
    cur = db.cursor()
    ready = None

    # DC motor
    mh = Raspi_MotorHAT(addr=0x6F)
    myMotor = mh.getMotor(2)

    # Servo motor
    pwm = PWM(0x6F)
    pwm.setPWMFreq(60)
    lock = Lock()  # Mutex

    if sys.argv[1] == "keyboard":
        # Thread Timer
        timer = None  # polling
        timer2 = None  # sensing
        timer3 = None  # DC
        timer4 = None  # servo

        speed = 0  # Motor speed
        velo = 0  # real speed (m/s)
        W, A, S, D = 0, 0, 0, 0  # Control key
        sense = SenseHat()  # SenseHat

        # Thread
        signal.signal(signal.SIGINT, closeDB)  # Finish
        polling()  # Data receive
        sensing()  # Data transmit
        DC()
        servo()

        # Main thread
        while True:
            sleep(0.05)
            if ready == None:
                continue

            W, A, S, D = ready
            ready = None

    elif sys.argv[1] == "phone":
        # Thread Timer
        timer = None  # polling_phone
        # timer2 = None  # sensing
        timer3 = None  # DC_phone
        timer4 = None  # servo_phone

        speed = 0  # Motor speed
        velo = 0  # real speed (m/s)
        broker_address = os.environ["BROKER_ADDR"]  # 라즈베리파이 #2의 IP 주소
        topic = os.environ["MQTT_TOPIC"]  # 토픽
        X, Y = 125, 125

        # Thread
        signal.signal(signal.SIGINT, closeDB)  # Finish
        mqtt_subscriber(broker_address, topic)
        # sensing()
        DC_phone()
        servo_phone()

        while True:
            sleep(0.05)
