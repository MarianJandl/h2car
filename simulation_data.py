import random
import time
import sys
import os
import datetime

tim = 0
di = 0
def generate_data():
    global tim, di
    
    tim += 1
    if random.randint(0, 4) == 3:
        a = random.randint(0, 25)
        if a >= 3 and a <= 7:
            di = 1
        elif a >= 7 and a <= 10:
            di = 3
        elif a >= 10 and a <= 13:
            di = 8
        elif a >= 13 and a <= 15:
            di = 9
        elif a >= 15 and a <= 18:
            di = 11
        else:
            di = 0
    
    return f"Tim:{tim} Di:{hex(di)} Pwm:0 Vbat:{round(random.random() * 2 + 7, 2)} Iout:{round(random.random() * 20 + 50, 2)} Pout:{round((random.random() * 20 + 50)*(random.random() * 2 + 7)*0.1, 2)} Vfc:{round(random.random() * 2 + 7, 2)} Pfc:{round((random.random() * 20 + 50)*(random.random() * 2 + 7)*0.1, 2)} PfcDes:{round((random.random() * 20 + 50)*(random.random() * 2 + 7)*0.1, 2)} Tfc:{random.randint(40, 80)}"

if not os.path.exists("logs"):
    os.mkdir("logs")

x = datetime.datetime.now().strftime("%Y%m%d")
k = 0


while os.path.exists(f"logs/simrawdatalog{x}_{k}.txt"):
    k += 1
with open(f"logs/simrawdatalog{x}_{k}.txt", "a") as f:
    f.write(f"--- New session started at {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---\n")

while True:
    try:
        data = generate_data()
        print("data:", data)
        with open(f"logs/simrawdatalog{x}_{k}.txt", "a") as f:
            f.write(data + "\n")
        sys.stdout.flush()
        time.sleep(1)
    except Exception as e:
        print("info:probably stopped ... or some error :)")
        print(e)
        exit()