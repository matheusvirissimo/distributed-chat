from socket import *
from threading import *

servidor_nome = '127.0.0.1'
porta_servidor = 5000

socket_cliente = socket(AF_INET, SOCK_STREAM)
socket_cliente.connect((servidor_nome, porta_servidor))


def receber_mensagens():
    while True:
        try:
            dados = socket_cliente.recv(1024)

            if not dados:
                
                print('\n--> A conexão com o servidor foi encerrada.')
                break

            mensagem = dados.decode('utf-8')
            print(f'\n{mensagem}')

        except:
            print('\n--> Ocorreu um erro na comunicação com o servidor. Conexão finalizada.')
            break


thread = Thread(target=receber_mensagens)
thread.daemon = True
thread.start()

while True:
    try:
        mensagem = input()

        socket_cliente.send(mensagem.encode('utf-8'))

        if mensagem == 'FIM':
            break

    except:
        break

socket_cliente.close()

