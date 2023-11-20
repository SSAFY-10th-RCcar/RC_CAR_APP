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

    if not -0.1 < acc < 0.1:
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

    if A == 1:
        pwm.setPWM(0, 0, 250)
    elif D == 1:
        pwm.setPWM(0, 0, 420)
    else:
        pwm.setPWM(0, 0, 355)
    lock.release()

    global timer4
    timer4 = Timer(0.05, servo)
    timer4.start()


if __name__=="__main__":
    # init
    db = mysql.connector.connect(
        host=os.environ["DB_HOST"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        database=os.environ["DB_SCHEMA"],
        auth_plugin=os.environ["AUTH_PLUGIN"],
    )
    cur = db.cursor()
    ready = None
    timer = None

    mh = Raspi_MotorHAT(addr=0x6F)
    myMotor = mh.getMotor(2)
    pwm = PWM(0x6F)
    pwm.setPWMFreq(60)

    sense = SenseHat()
    timer2 = None
    lock = Lock()
    timer3 = None
    timer4 = None
    speed = 0
    velo = 0

    W, A, S, D = 0, 0, 0, 0

    signal.signal(signal.SIGINT, closeDB)
    polling()
    sensing()
    DC()
    servo()

    # main thread
    while True:
        sleep(0.1)
        if ready == None:
            continue

        W, A, S, D = ready
        ready = None

