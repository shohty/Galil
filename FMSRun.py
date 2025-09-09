
import socket
import gclib
import time
import logging
import os
import threading
from datetime import datetime


#CONFIG FILE READING
def read_config(file_path):
    config = {}
    with open(file_path, 'r') as file:
        for line in file:
            key, value = line.strip().split('=')
            config[key] = value
    return config

config = read_config(r'/Users/shohtatakami/github/galil/config.txt')

# Config values
IP = config['IP'] 
port = int(config['port'])
logDirectory = config['logDirectory']
galilAddress = config['galilAddress']
cfA = float(config['cfA'])
cfB = float(config['cfB'])
speedA = int(config['speedA'])
speedB = int(config['speedB'])

print(f"Galil Address: {galilAddress}")
    
#Log directory and name
timestamp = datetime.now().strftime('%Y-%m-%d_%H')
log_directory = rf'{logDirectory}'
log_filename = f'server_log_{timestamp}.txt'
log_path = os.path.join(log_directory, log_filename)

#Configure logging
logging.basicConfig( 
    filename = log_path,
    filemode = 'a',
    level = logging.INFO,
    format = '%(asctime)s - %(levelname)s - %(message)s'
    )

#GClib for Galil
g = gclib.py()
g.GOpen(address=f'{galilAddress}')
c = g.GCommand

#Initial Conditions
cfA = float(cfA)
cfB = float(cfB)

# 新しい関数: 10cm移動
def move(distance):
    """A軸を10cm（100mm）移動する関数"""
    try:
        print("Starting 10cm movement...")
        logging.info("Starting 10cm movement...")
        
        # A軸サーボオン
        c('SHA')
        
        # 移動量を設定（100mm）
        posAMove = distance * (1/cfA)  # Galil内部単位に変換
        
        # 速度設定
        c(f'JG-{speedA}')
        
        # 目標位置設定
        c(f'PA{posAMove}')
        
        print(f'Moving A-axis ({distance}mm) to position {posAMove} units')
        logging.info(f'Moving A-axis ({distance}mm) to position {posAMove} units')
        
        # 移動開始
        c('BGA')
        
        # 移動完了まで待機
        while float(c('MG _BGA')) > 0:
            time.sleep(0.1)
        
        print("10cm movement completed!")
        logging.info("10cm movement completed!")
        
        return True
        
    except Exception as e:
        print(f"Error in move_10cm: {e}")
        logging.error(f"Error in move_10cm: {e}")
        return False


#PYTHON -> GALIL
def handle_client(client_socket, addr):
    global speedA, speedB, cfA, cfB
    try:
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
            print(f"Received: {data.decode('utf-8')}")
            logging.info(f"Received: {data.decode('utf-8')}")

            #Commands:

            ##HOME##
            if 'HOME' in data.decode('utf-8'):
                c('SHAB')
                g.GCommand('XQ#HOMEA,1')
                print('Homing A')
                logging.info('Homing A')
                g.GCommand('XQ#HOMEB,2')
                print('Homing B')
                logging.info('Homing B')
                while float(c('MG _XQ'))>0 or float(c('MG _BGA')) > 0 or float(c('MG _BGB')) > 0:
                    time.sleep(5)
                c('HX1')
                c('HX2')

            ##STATUS##
            if 'STATUS' in data.decode('utf-8'):

                posA = str(((float(c('MG _TPA'))*cfA)))
                posB = str(float(c('MG _TPB'))*cfB)
                       
                FLSA = 'F'
                FLSB = 'F'
                RLSA = 'F'
                RLSB = 'F'

                if float(c('MG _LFA')) > 0:
                    FLSA = 'F'
                else:
                    FLSA = 'T'

                if float(c('MG _LRA')) > 0:
                    RLSA = 'F'
                else:
                    RLSA = 'T'

                if float(c('MG _LFB')) > 0:
                    FLSB = 'F'
                else:
                    FLSB = 'T'

                if float(c('MG _LRB')) > 0:
                    RLSB = 'F'
                else:
                    RLSB = 'T'

                if float(c('MG _BGB')) > 0:
                    ready = 'MOVING'
                elif float(c('MG _BGA')) > 0:
                    ready = 'MOVING'
                else:
                    ready = "STATIONARY"

                CHcount = str(len(f'STATUS {ready} {posA},{posB} {FLSA}{RLSA}{FLSB}{RLSB} {RLSA}{RLSB}'))
                message = f'   {CHcount}STATUS {ready} {posA},{posB} {FLSA}{RLSA}{FLSB}{RLSB} {RLSA}{RLSB}'
                   
                next_message=None

                client_socket.sendall(message.encode('utf-8'))
                print(message)
                logging.info(message)

            ##SPEED##
            if 'SPEED' in data.decode('utf-8'):      
                parts = data.decode('utf-8').strip(' ').split(' ')
                speeds = parts[1].split(',')
                speedA = (speeds[0])*(1/cfA)
                speedB = (speeds[1])*(1/cfB)      

            ##MOVE##
            elif 'MOVE' in data.decode('utf-8'):
                c('SHA')
                parts=data.decode('utf-8').strip(' ').split(' ')
                moveAMT= float(parts[1])
                posAMove = moveAMT*(1/cfA)
                c(f'JG-{speedA}')
                print(f'{posAMove}')
                logging.info(f'{posAMove}')
                c(f'PA{posAMove}')
                print(f'Moving to {moveAMT} (mm)')
                logging.info(f'Moving to {moveAMT} (mm)')
                print(f'Moving to {posAMove} (units)')
                logging.info(f'Moving to {posAMove} (units)')
                c('BGA')
                time.sleep(1)
                client_socket.sendall(('ACK').encode('utf-8'))

            ##ROTATE##          
            elif 'ROTATE' in data.decode('utf-8'):
                c('SHB')
                c(f'JG,{speedB}')
                parts=data.decode('utf-8').strip(' ').split(' ')
                rotateAMT=float(parts[1])
                posBMove = rotateAMT*(1/cfB)
                print(f'{posBMove}')
                logging.info(f'{posBMove}')
                c(f'PA,{posBMove}')
                c('BGB')
                     
            ##ABORT##
            if 'ABORT' in data.decode('utf-8'):
                c('ST AB')

            ##ENABLE##
            if 'ENABLE' in data.decode('utf-8'):
                c('SHAB')
                   
    except socket.error as e:
        a=1
        print(f"Socket error: {e}")
    finally:
        client_socket.close()
        print(f"Connection closed with {addr}")
        logging.info(f"Connection closed with {addr}")
               

################################################################################

#EMMA -> Python
def start_server(host=f'{IP}', port=port):
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind((host, port))
    server_socket.listen(5)
    print(f"Server listening on {host}:{port}")
    logging.info(f"Server listening on {host}:{port}")
   
    try:
        while True:
            client_socket, addr = server_socket.accept()
            print(f"Connection established with {addr}")
            logging.info(f"Connection established with {addr}")
            threading.Thread(target=handle_client, args=(client_socket,addr)).start()
    except KeyboardInterrupt:
        print('server shutting down')
        logging.info("Server shutting down")
    finally:
        server_socket.close()


############################################################################

threading.Thread(target=start_server).start()

logging.shutdown()
