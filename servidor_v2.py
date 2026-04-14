from socket import *
from threading import *

porta_servidor = 5000
socket_servidor = socket(AF_INET, SOCK_STREAM)

socket_servidor.setsockopt(SOL_SOCKET, SO_REUSEADDR, 1)
socket_servidor.bind(('', porta_servidor))

socket_servidor.listen(5)
print('O servidor está pronto para receber')

clientes = {}

lock_clientes = Lock()

def broadcast(mensagem, socket_ignorado):
    with lock_clientes:
        for nome, socket_cliente in list(clientes.items()):
            if socket_cliente != socket_ignorado:
                try:
                    socket_cliente.send(mensagem.encode('utf-8'))
                except:
                    pass

def unicast(remetente, destino, mensagem):
    with lock_clientes:
        if destino in clientes:
            try:
                texto = f'[Mensagem privada de {remetente}] {mensagem}'
                clientes[destino].send(texto.encode('utf-8'))
                return True
            except:
                return False
        return False


def remover_cliente(nome):
    with lock_clientes:
        if nome in clientes:
            del clientes[nome]


def atender_cliente(conexaoSocket, endereco):
    nome_cliente = None

    try:
        while True:
            conexaoSocket.send('Digite seu nome: '.encode('utf-8'))
            nome_cliente = conexaoSocket.recv(1024).decode('utf-8').strip()

            with lock_clientes:
                if not nome_cliente or nome_cliente in clientes:
                    conexaoSocket.send('Este nome de usuário é inválido ou já está em uso. Por favor, escolha outro.\n'.encode('utf-8'))
                    continue

                clientes[nome_cliente] = conexaoSocket
                break

        print(f'Conexão estabelecida com {endereco}. Usuário registrado: {nome_cliente}')
        broadcast(f'O usuário {nome_cliente} ingressou no sistema de bate-papo.', None)

        conexaoSocket.send(
            'Bem-vindo ao sistema de bate-papo!\n'
            '-> Para enviar uma mensagem privada, utilize o formato: /p nome_do_usuario mensagem\n'
            '-> Exemplo: /p Mazzaro Olá, tudo bem?\n'
            '-> Para encerrar a sessão, digite: FIM\n'.encode('utf-8')
        )

        while True:
            dados = conexaoSocket.recv(1024)

            if not dados:
                print(f'{nome_cliente} desconectou.')
                break

            mensagem = dados.decode('utf-8').strip()

            if mensagem == 'FIM':
                break

            if mensagem.startswith('/p '):
                partes = mensagem.split(' ', 2)

                if len(partes) < 3:
                    conexaoSocket.send('Formato inválido. Por favor, utilize a estrutura: /p nome_do_usuario mensagem'.encode('utf-8'))
                    continue

                destino = partes[1]
                mensagem_privada = partes[2]

                sucesso = unicast(nome_cliente, destino, mensagem_privada)

                if sucesso:
                    conexaoSocket.send(f'[Mensagem privada enviada com sucesso para {destino}] {mensagem_privada}'.encode('utf-8'))
                else:
                    conexaoSocket.send(f'Erro: O usuário "{destino}" não foi encontrado no sistema.'.encode('utf-8'))

            else:
                mensagem_aberta = f'[{nome_cliente}] {mensagem}'
                print(mensagem_aberta)
                broadcast(mensagem_aberta, None)

    except Exception as erro:
        print(f'Erro com o cliente {endereco}: {erro}')

    finally:
        if nome_cliente is not None:
            remover_cliente(nome_cliente)
            print(f'{nome_cliente} saiu.')
            broadcast(f'{nome_cliente} saiu.', conexaoSocket)

        conexaoSocket.close()


while True:
    conexaoSocket, endereco = socket_servidor.accept()
    print(f'Nova conexão de {endereco}')

    thread = Thread(target = atender_cliente, args = (conexaoSocket, endereco))
    thread.start()


