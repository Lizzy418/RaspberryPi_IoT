#-*-coding:utf-8-*-

# 필요한 라이브러리를 불러옵니다. 
import RPi.GPIO as GPIO
from flask import Flask, render_template, request
from flask_bootstrap import Bootstrap
# import mysql.connector
import pymysql
from datetime import datetime
import time
import threading

app = Flask(__name__)
Bootstrap(app) #이렇게 해줘야 적용됨

#DB Connect
#Maria = mysql.connector.connect(host="localhost", user="root", passwd="860508", database="led_db")
Maria = pymysql.connect(host="localhost", user="root", passwd="860508", database="led_db")
Cursor = Maria.cursor()

# 불필요한 warning 제거,  GPIO핀의 번호 모드 설정
GPIO.setwarnings(False)  
GPIO.setmode(GPIO.BCM)

# pins란 딕셔너리를 만들고 GPIO 23, 24, 25 핀을 저장합니다.
pins = {
   23 : {'name' : 'Red LED', 'state' : GPIO.LOW},
   24 : {'name' : 'Yellow LED', 'state' : GPIO.LOW},
   25 : {'name' : 'Green LED', 'state' : GPIO.LOW}
}

# pins 내에 있는 모든 핀들을 출력으로 설정하고 초기 LED OFF 설정
for pin in pins:
   GPIO.setup(pin, GPIO.OUT)
   GPIO.output(pin, GPIO.LOW)

# LED 사용 시간 출력(오늘 기준)
def usingLED():
   #켜고 끈 시간이 모두 오늘인 경우
   Query = "SELECT Name, TIMESTAMPDIFF(MINUTE, onTime, offTime) AS TIMESTAMPDIFF from tLED \
   where DATE_FORMAT(offTime, '%Y-%m-%d') = CURDATE() \
   AND DATE_FORMAT(onTime, '%Y-%m-%d') = CURDATE()"
   Cursor.execute(Query)
   tdataList = Cursor.fetchall()
   #어제 켰는데 오늘 끈 경우(자정에 테스트 필요)
   Query2 = "SELECT Name, TIMESTAMPDIFF(MINUTE, DATE_FORMAT(now(), '%Y-%m-%d 00:00:00'), offTime) AS TIMESTAMPDIFF from tLED \
   where DATE_FORMAT(offTime, '%Y-%m-%d') = CURDATE() \
   AND DATE_FORMAT(onTime, '%Y-%m-%d') = CURDATE() - INTERVAL 1 DAY"
   Cursor.execute(Query2)
   tdataList = tdataList + Cursor.fetchall()
   usingList = list()
   for pin in pins:
      total = 0
      for i in tdataList: #select한 데이터들 딕셔너리
         if pins[pin]['name'] == i[0]: #이름이 같은 위치에다 더하기
            if i[1] != 0 and i[1]:
               total = total+i[1]
      usingList.append([pins[pin]['name'], total])
   return usingList

#LED 사용 시간 출력(한달 기준)
def usingLEDm():
   #on/off 모두 이번달만 조회
   Query = "SELECT Name, TIMESTAMPDIFF(MINUTE, onTime, offTime) AS TIMESTAMPDIFF from tLED \
   where Month(offTime) = Month(now()) AND Month(onTime) = Month(now())"
   Cursor.execute(Query)
   tdataList = Cursor.fetchall()
   #달 마지막에 on 해서 다음 달에 off 된 경우(테스트 필요)
   Query2 = "SELECT Name, TIMESTAMPDIFF(MINUTE, DATE_FORMAT(now(), '%Y-%m-%d 00:00:00'), offTime) AS TIMESTAMPDIFF from tLED \
   where Month(offTime) = Month(now()) \
   AND Month(offTime) = Month(now()) - INTERVAL 1 MONTH"
   Cursor.execute(Query2)
   tdataList = tdataList + Cursor.fetchall()
   usingList2 = list()
   for pin in pins:
      total = 0
      for i in tdataList: #select한 데이터들 딕셔너리
         if pins[pin]['name'] == i[0]: #이름이 같은 위치에다 더하기
            if i[1] != 0 and i[1]:
               total = total+i[1]
      usingList2.append([pins[pin]['name'], total])
   return usingList2

# 웹서버의 URL 주소로 접근하면 아래의 main() 함수를 실행
@app.route("/")
def main():
   # pins 내에 있는 모든 핀의 현재 핀 상태(ON/OFF)를 업데이트
   for pin in pins:
      pins[pin]['state'] = GPIO.input(pin)
   # tmplateData 에 저장
   templateData = {
      'pins' : pins
      }
   # 업데이트 된 templateDate 값들을 homeLED.html로 리턴
   return render_template('homeLED.html', **templateData, usingList = usingLED(), usingList2 = usingLEDm() )

# led가 켜졌을 때 db에 저장
def insert_data(changePin):
   CheckTime = "SELECT onTime, offTime from tLED where Name=%s"
   Name = [ (pins[changePin]['name']) ]
   Cursor.execute(CheckTime, Name)
   cTime = Cursor.fetchall()
   d = datetime.today().strftime('%Y-%m-%d %H:%M:%S')    #현재시간
   Query = "INSERT INTO tLED(Name, onTime) VALUES(%s, %s)"
   Values = [
      ( pins[changePin]['name'], d )
   ]
   #아예 처음 DB에 넣는 경우
   if not cTime :  
      Cursor.executemany(Query, Values)
      Maria.commit()
   #off한 시간도 모두 들어가있는 경우(on만 데이터가 들어간 경우엔 새로 추가되지 않게)
   else:
      if cTime[-1][-1]:
         Cursor.executemany(Query, Values)
         Maria.commit()

# led가 꺼졌을 때 해당 db 업데이트
def update_data(changePin):
   d = datetime.today().strftime('%Y-%m-%d %H:%M:%S')
   Query = "UPDATE tLED SET offTime=%s where Name=%s AND offTime IS NULL"
   Values = [
      (d, pins[changePin]['name']) 
   ]
   Cursor.executemany(Query, Values)
   Maria.commit()

# URL 주소 끝에 “/핀번호/<action>”을 붙여서 접근시에 action 값에 따라 동작
@app.route("/<changePin>/<action>")
def action(changePin, action):
   # 현재 핀번호를 URL 주소로 받은 핀번호로 설정
   changePin = int(changePin)
   # 핀번호에 설정된 이름값을 불러옴
   deviceName = pins[changePin]['name']
   # action 값이 ‘on’일때
   if action == "on":
      GPIO.output(changePin, GPIO.HIGH)
   # action 값이 ‘off’일때
   if action == "off":
      GPIO.output(changePin, GPIO.LOW)
   # GPIO 핀의 ON/OFF 상태 저장
   pins[changePin]['state'] = GPIO.input(changePin)
   if pins[changePin]['state']==True:
      insert_data(changePin)
   else:
      update_data(changePin)
   # 핀들의 값들을 업데이트 해서 pinData에 저장
   pinData = {
      'pins' : pins
   }
   # 업데이트 된 pinData 값들을 homeLED.html로 리턴
   return render_template('homeLED.html', **pinData, usingList = usingLED(), usingList2 = usingLEDm() )

#DB 리스트 웹페이지에 띄우기
@app.route("/list")
def lists():
   Query = "SELECT * from tLED"
   Cursor.execute(Query)
   dataList = Cursor.fetchall()
   #페이지 값 (디폴트 = 1)
   #page = request.args.get('page', type=int, default=1)
   return render_template('list.html', dataList=dataList)

@app.route("/list/<selectPin>")
def selectPin(selectPin):
   selectPin = str(selectPin)
   if selectPin == "Red":
      Query = "SELECT * from tLED where Name='Red LED'"
   if selectPin == "Yellow":
      Query = "SELECT * from tLED where Name='Yellow LED'"
   if selectPin == "Green":
      Query = "SELECT * from tLED where Name='Green LED'"
   Cursor.execute(Query)
   dataList = Cursor.fetchall()
   return render_template('list.html', dataList=dataList)

@app.route("/about")
def about():
	return render_template('about.html')


if __name__ == "__main__":
   app.run(host='0.0.0.0', port=5000, debug=True)
