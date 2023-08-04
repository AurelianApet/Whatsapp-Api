async_mode = 'eventlet'

import eventlet
import eventlet.wsgi
import json
import random
import urllib3
import requests
import time

from datetime import datetime
from pytz import timezone

from  time import gmtime,strftime
from flask import Flask, render_template, Response, request, send_file
from webwhatsapi import WhatsAPIDriver
from webwhatsapi import WhatsAPIDriverStatus
from webwhatsapi.objects.message import Message
from flask import jsonify
import _thread
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret!'
drivers={}

def time_formart_to_seconds(txt_time):
    time_array = txt_time.split(':')
    return int(time_array[0])*3600 + int(time_array[1])*60

def reponse_for_working_time(uid_token, user_id,driver,sender_id,db,cursor):
    static_path = 'C:/Work/WhatsApp/whatsAppApiSite/storage/app/public/'
    cursor.execute("SELECT * FROM working_times WHERE user_id=\'" + user_id + "\'")
    working_time  = cursor.fetchall()

    now_utc = datetime.now(timezone('UTC'))
    now_asia = now_utc.astimezone(timezone('America/Mexico_City'))
    current_day = now_asia.strftime("%w")

    current_senconds = time_formart_to_seconds(now_asia.strftime("%H:%M:%S"))
    for one_working_time in working_time:
        day_range = one_working_time[2].split('~')
        time_range = one_working_time[3].split('~')
        if int(day_range[0]) < int(current_day) and int(day_range[1]) > int(current_day) and time_formart_to_seconds(time_range[0]) < current_senconds and time_formart_to_seconds(time_range[1]) > current_senconds:
            if(one_working_time[4] == 'text'):
                driver.send_message_to_id(sender_id,one_working_time[5])
            else:
                driver.send_media(static_path + one_working_time[7],sender_id,one_working_time[5])
            update_write_message(db,cursor,uid_token)
    return True    

def response_message( uid_token,driver,sender_id,db,cursor):
    static_path = 'C:/Work/WhatsApp/whatsAppApiSite/storage/app/public/'
    cursor.execute("SELECT * FROM users WHERE token=\'" + uid_token + "\'")
    user = cursor.fetchall()
    user_id = user[0][0]
    phone = user[0][9]
    cursor.execute("SELECT * FROM auto_response_messages WHERE user_id=\'" + str(user_id) + "\'")
    response_msg = cursor.fetchall()
    if len(response_msg) != 0:
        if(response_msg[0][2] == 'text'):
            driver.send_message_to_id(sender_id,response_msg[0][3])
        else:
            driver.send_media(static_path + response_msg[0][5],sender_id,response_msg[0][3])
        insert_chat_id_sql = "INSERT INTO chat_ids (user_id , phone , chat_id) VALUES (%s, %s, %s)"
        val = (str(user_id),phone,sender_id)
        cursor.execute(insert_chat_id_sql,val)
        db.commit()
        update_write_message(db,cursor,uid_token)
    return True

def update_write_message(db,cursor,uid_token):
    cursor.execute("SELECT * FROM users WHERE token=\'" + uid_token + "\'")
    user = cursor.fetchall()
    user_id = user[0][0]
    write_message = cursor.execute("SELECT * from statis WHERE user_id=\'" + str(user_id) + "\'")
    static = cursor.fetchall()
    if len(static) != 0:
        write_messages = int(static[0][1])
        write_messages = write_messages + 1
        qeury_update_write_messages = "UPDATE statis SET sent_message = \'"+str(write_messages)+"\' WHERE user_id = \'" + str(user_id) + "\'"
        cursor.execute(qeury_update_write_messages)
        db.commit()
    return True

def update_read_message(db,cursor,uid_token):
    cursor.execute("SELECT * FROM users WHERE token=\'" + uid_token + "\'")
    user = cursor.fetchall()
    user_id = user[0][0]
    read_message = cursor.execute("SELECT * from statis WHERE user_id=\'" + str(user_id) + "\'")
    static = cursor.fetchall()
    if len(static) != 0:
        read_messages = int(static[0][2])
        read_messages = read_messages + 1
        qeury_update_read_messages = "UPDATE statis SET read_message = \'"+str(read_messages)+"\' WHERE user_id = \'" + str(user_id) + "\'"
        cursor.execute(qeury_update_read_messages)
        db.commit()
    return True

def get_working_message(uid_token):
    driver = drivers[uid_token]
    whats_app_db = mysql.connector.connect(host='localhost',database='whats_app',user='root',password='')        
    cursor = whats_app_db.cursor()
    query_running_service = "UPDATE users SET working_thread = 'running' WHERE token = \'" + uid_token + "\'"
    cursor.execute(query_running_service)
    whats_app_db.commit()
    cursor.execute("SELECT * FROM users WHERE token=\'" + uid_token + "\'")
    user = cursor.fetchall()
    user_id = user[0][0]
    
    try:
        while True:
            time.sleep(1)
            for contact in driver.get_unread():
                for message in contact.messages:
                    if isinstance(message, Message):  # Currently works for text messages only.
                        plan_sql = "SELECT * from plans WHERE user_id=\'" + str(user_id) + "\'"
                        cursor.execute(plan_sql)
                        plans = cursor.fetchall()
                        if len(plans) != 0:
                            read_num = int(plans[0][2])
                            write_num = int(plans[0][3])
                            cursor.execute("SELECT * FROM statis WHERE user_id=\'" + str(user_id) + "\'")
                            statics = cursor.fetchall()
                            sent_message = int(statics[0][1])
                            read_message = int(statics[0][2])
                            if read_num >= read_message:
                                insert_sql = "INSERT INTO unread_messages (user_id , timestamp , user_phone , content) VALUES (%s, %s, %s, %s)"
                                if len(message.content) > 1000:
                                    message.content = message.caption + '(This is a media file.Please check it in whatsapp)'
                                val = (user_id,message.timestamp.timestamp(),message.sender.id,message.content)
                                cursor.execute(insert_sql,val)
                                whats_app_db.commit()
                                update_read_message(whats_app_db,cursor,uid_token)                    
                            if write_num >= sent_message:
                                auto_response_sql = "SELECT * from auto_response_messages WHERE user_id=\'" + str(user_id) + "\'"
                                cursor.execute(auto_response_sql)
                                auto_responses = cursor.fetchall()
                                reponse_for_working_time(uid_token,str(user_id),driver,message.sender.id,whats_app_db,cursor)
            cursor.execute("SELECT working_thread FROM users WHERE token=\'" + uid_token + "\'")
            user = cursor.fetchall()
            service_status = user[0][0]   
            if service_status == '_stop':
                stop_running_service = "UPDATE users SET working_thread = 'stop' WHERE token = \'" + uid_token + "\'"
                cursor.execute(stop_running_service)
                whats_app_db.commit()
                break;
            else:
                query_running_service = "UPDATE users SET working_thread = 'running' WHERE token = \'" + uid_token + "\'"
                cursor.execute(query_running_service)
                whats_app_db.commit()
    except Exception as e:
        query_running_service = "UPDATE users SET working_thread = 'stop' WHERE token = \'" + uid_token + "\'"
        cursor.execute(query_running_service)
        whats_app_db.commit()
    cursor.close()
    whats_app_db.close()

def get_read_message(uid_token):
    driver = drivers[uid_token]
    whats_app_db = mysql.connector.connect(host='localhost',database='whats_app',user='root',password='')        
    cursor = whats_app_db.cursor()
    query_running_service = "UPDATE users SET thread = 'running' WHERE token = \'" + uid_token + "\'"
    cursor.execute(query_running_service)
    whats_app_db.commit()
    cursor.execute("SELECT * FROM users WHERE token=\'" + uid_token + "\'")
    user = cursor.fetchall()
    user_id = user[0][0]
    
    try:
        while True:
            time.sleep(1)
            for contact in driver.get_unread():
                for message in contact.messages:
                    if isinstance(message, Message):  # Currently works for text messages only.
                        plan_sql = "SELECT * from plans WHERE user_id=\'" + str(user_id) + "\'"
                        cursor.execute(plan_sql)
                        plans = cursor.fetchall()
                        if len(plans) != 0:
                            read_num = int(plans[0][2])
                            write_num = int(plans[0][3])
                            cursor.execute("SELECT * FROM statis WHERE user_id=\'" + str(user_id) + "\'")
                            statics = cursor.fetchall()
                            sent_message = int(statics[0][1])
                            read_message = int(statics[0][2])
                            if read_num >= read_message:
                                insert_sql = "INSERT INTO unread_messages (user_id , timestamp , user_phone , content) VALUES (%s, %s, %s, %s)"
                                if len(message.content) > 1000:
                                    message.content = message.caption + '(This is a media file.Please check it in whatsapp)'
                                val = (user_id,message.timestamp.timestamp(),message.sender.id,message.content)
                                cursor.execute(insert_sql,val)
                                whats_app_db.commit()
                                update_read_message(whats_app_db,cursor,uid_token)                    
                            if write_num >= sent_message:
                                auto_response_sql = "SELECT * from auto_response_messages WHERE user_id=\'" + str(user_id) + "\'"
                                cursor.execute(auto_response_sql)
                                auto_responses = cursor.fetchall()
                                if len(auto_responses) != 0:
                                    if auto_responses[0][6]:
                                        cursor.execute("SELECT * from chat_ids WHERE chat_id=\'" + message.sender.id + "\'")
                                        same_chat_id = cursor.fetchall()
                                        if len(same_chat_id) == 0:
                                            response_message(uid_token,driver,message.sender.id,whats_app_db,cursor)
                                    else:
                                        response_message(uid_token,driver,message.sender.id,whats_app_db,cursor)     
            cursor.execute("SELECT thread FROM users WHERE token=\'" + uid_token + "\'")
            user = cursor.fetchall()
            service_status = user[0][0]   
            if service_status == '_stop':
                stop_running_service = "UPDATE users SET thread = 'stop' WHERE token = \'" + uid_token + "\'"
                cursor.execute(stop_running_service)
                whats_app_db.commit()
                break;
            else:
                query_running_service = "UPDATE users SET thread = 'running' WHERE token = \'" + uid_token + "\'"
                cursor.execute(query_running_service)
                whats_app_db.commit()

    except Exception as e:
        query_running_service = "UPDATE users SET thread = 'stop' WHERE token = \'" + uid_token + "\'"
        cursor.execute(query_running_service)
        whats_app_db.commit()
    cursor.close()
    whats_app_db.close()

def checkLogin(uid_token):
    exist = False
    try:
        check = drivers[uid_token]
        exist = True
    except KeyError as e:
        exist = False
    if exist:
        driverStatus = check.get_status()
        if driverStatus == WhatsAPIDriverStatus.LoggedIn:
            res = {'result': 'Exist','status':'loggedIn'}
            #create_read_thread(uid_token)
        if driverStatus == WhatsAPIDriverStatus.NotLoggedIn:
            res = {'result': 'Exist','status':'notLoggedIn'}
        if driverStatus == WhatsAPIDriverStatus.Unknown:
            res = {'result': 'Exist','status':'unknown'}
        if driverStatus == WhatsAPIDriverStatus.NoDriver:
            res = {'result': 'Exist','status':'noDriver'}
        if driverStatus == WhatsAPIDriverStatus.NotConnected:
            res = {'result': 'Exist','status':'notConnected'}
    else:
        res = {'result': 'noExist','status':'There is not driver'}
    return res

@app.route('/createInstance',methods=['POST'])
def createInstance():
    uid_token = request.values['uid_token']
    user_name = request.values['user_name']
    exist = False
    try:
        check = drivers[uid_token]
        exist = True
    except KeyError as e:
        exist = False
    if exist:
        driverStatus = check.get_status()
        if driverStatus == WhatsAPIDriverStatus.LoggedIn:
            res = {'result': 'Exist','status':'loggedIn'}
        if driverStatus == WhatsAPIDriverStatus.NotLoggedIn:
            res = {'result': 'Exist','status':'notLoggedIn'}
        if driverStatus == WhatsAPIDriverStatus.Unknown:
            res = {'result': 'Exist','status':'unknown'}
        if driverStatus == WhatsAPIDriverStatus.NoDriver:
            res = {'result': 'Exist','status':'noDriver'}
        if driverStatus == WhatsAPIDriverStatus.NotConnected:
            res = {'result': 'Exist','status':'notConnected'}
    else:
        driver = WhatsAPIDriver(username=user_name,loadstyles=True)
        qr_file_path = driver.get_qr(filename=uid_token + '.png')
        drivers[uid_token] = driver
        return send_file(uid_token + ".png",mimetype='image/png')
    return jsonify(res)

@app.route('/run_unread_service',methods=['POST'])
def runUnreadService():
    uid_token = request.values['uid_token']
    res = checkLogin(uid_token=uid_token)
    if res['status'] == 'loggedIn':
        driver = drivers[uid_token]
        res = {'result': 'success'}
        try:
            _thread.start_new_thread(get_read_message,(uid_token,))
        except Exception as e:
            res = {'result': 'fail'}
    return jsonify(res)

@app.route('/run_working_service',methods=['POST'])
def runWorkingService():
    uid_token = request.values['uid_token']
    res = checkLogin(uid_token=uid_token)
    if res['status'] == 'loggedIn':
        driver = drivers[uid_token]
        res = {'result': 'success'}
        try:
            _thread.start_new_thread(get_working_message,(uid_token,))
        except Exception as e:
            res = {'result': 'fail'}
    return jsonify(res)

@app.route('/checkLoginStatus',  methods=['POST'])
def checkLoginStatus():
    uid_token = request.values['uid_token']
    exist = False
    try: 
        check = drivers[uid_token]
        exist = True
    except KeyError as e:
        exist = False
    if exist:
        if exist:
            driverStatus = check.get_status()
        if driverStatus == WhatsAPIDriverStatus.LoggedIn:
            res = {'result': 'Exist','status':'loggedIn'}
        if driverStatus == WhatsAPIDriverStatus.NotLoggedIn:
            res = {'result': 'Exist','status':'notloggedIn'}
        if driverStatus == WhatsAPIDriverStatus.Unknown:
            res = {'result': 'Exist','status':'unknown'}
        if driverStatus == WhatsAPIDriverStatus.NoDriver:
            res = {'result': 'Exist','status':'noDriver'}
        if driverStatus == WhatsAPIDriverStatus.NotConnected:
            res = {'result': 'Exist','status':'notConnected'}
    else:
        res = {'result': 'noExist','status':'There is not driver'}
    return jsonify(res)

@app.route('/getQrCode',  methods=['POST'])
def getQrCode():
    uid_token = request.values['uid_token']
    exist = False
    try: 
        check = drivers[uid_token]
        exist = True
    except KeyError as e:
        exist = False
    if exist:
        try:
            qr_file_path = check.get_qr(filename=uid_token + '.png')
        except:
            return jsonify({'result': 'logined','status':'Whatsapp is logined now'})
        return send_file(uid_token + ".png",mimetype='image/png')
    else:
        res = {'result': 'noExist','status':'There is not driver'}
    return jsonify(res)

@app.route('/destoryInstance',methods=['POST'])
def destoryInstance():
    uid_token = request.values['uid_token']
    exist = False
    try:
        check = drivers[uid_token]
        check.close()
        exist = True
    except KeyError as e:
        exist = False
    if exist:
        del drivers[uid_token]
        res = {'result': 'success','status':'The driver removed'}
    else:
        res = {'result': 'noExist','status':'There is not driver'}
    return jsonify(res)

@app.route('/sendMessage',methods=['POST'])
def sendMessage():
    uid_token = request.values['uid_token']
    chat_id = request.values['chat_id']
    res = checkLogin(uid_token=uid_token)
    if res['status'] == 'loggedIn':
        driver = drivers[uid_token]
        message = request.values['message']
        try:
            driver.send_message_to_id(chat_id,message)
            res = {'result':'success'}
        except Exception as e:
            res = {'result': 'fail'}
    return jsonify(res)

@app.route('/sendMedia',methods=['POST'])
def sendMedia():
    uid_token = request.values['uid_token']
    res = checkLogin(uid_token=uid_token)
    if res['status'] == 'loggedIn':
        driver = drivers[uid_token]
        message = request.values['message']
        chat_id = request.values['chat_id']
        file_name = request.values['file_name'];
        try:
            driver.send_media(file_name,chat_id,message)
            res = {'result':'success'}
        except Exception as e:
            res = {'result':'fail'}
    return jsonify(res)

@app.route('/getChatIds',methods=['POST'])
def getChatIds():
    uid_token = request.values['uid_token']
    res = checkLogin(uid_token=uid_token)
    if res['status'] == 'loggedIn':
        driver = drivers[uid_token]
        chat_ids = driver.get_all_chat_ids()
        res = {'result': 'success','chat_ids':''}
        for chat_id in chat_ids:
            res['chat_ids'] += chat_id
    return jsonify(res)

@app.route('/getChatNames',methods=['POST'])
def getChatNames():
    uid_token = request.values['uid_token']
    res = checkLogin(uid_token=uid_token)
    if res['status'] == 'loggedIn':
        driver = drivers[uid_token]
        chat_ids = driver.get_all_chats()
        res = {'result': 'success','chat_ids':[]}
        for chat_id in chat_ids:
            res['chat_ids'].append({'chat_id':chat_id.id,'name':chat_id.name})
    return jsonify(res)

@app.route('/getAllChats',methods=['POST'])
def getAllChats():
    uid_token = request.values['uid_token']
    chat_id = request.values['chat_id']
    res = checkLogin(uid_token=uid_token)
    if res['status'] == 'loggedIn':
        driver = drivers[uid_token]
        res = {'result':'success','chat_info':[]}
        chat = driver.get_chat_from_id(chat_id)
        all_messages = driver.get_all_message_ids_in_chat(chat,True,False)
        for message_id in all_messages:
            message = driver.get_message_by_id(message_id)
            if message.sender.formatted_name == 'You':
                message.sender.name = 'me'
            else:
                message.sender.name = message.sender.formatted_name
            try:
                res['chat_info'].append({'sender':message.sender.name+':'+message.sender.id,'time':message.timestamp.timestamp(),'content':message.content,'caption':message.caption})
            except Exception as e:
                try:
                    res['chat_info'].append({'sender':message.sender.name+':'+message.sender.id,'time':message.timestamp.timestamp(),'content':message.content})
                except Exception as e1:
                    res['chat_info'].append({'sender':message.sender.name+':'+message.sender.id,'time':message.timestamp.timestamp(),'content':'This is sticker.(Please check it in whatsapp.)'})
    return jsonify(res)

if __name__ == '__main__':
    eventlet.wsgi.server(eventlet.listen(('', 8088)), app)
