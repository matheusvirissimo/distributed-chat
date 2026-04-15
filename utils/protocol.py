"""
Módulo de protocolo compartilhado entre cliente e servidor.

Define as estruturas de mensagens, identificadores de operações e
modos de comunicação usados no sistema de chat distribuído com RPC/RMI.
"""

import json
import uuid


# Identificadores de Operação (OperationId)

class OperacaoId:
    """
    Constantes que identificam cada operação remota disponível no sistema
    (Em resumo, são as operações listadas no PDF)

    Constants
    ----------
    ENVIAR_MENSAGEM : str
        Transmissão da mensagem para todos os usuários conectados
    MENSAGEM_PRIVADA : str
        Envio de mensagem privada para um usuário específico
    LISTAR_USUARIOS : str
        Listagem usuários *atualmente* conectados
    ENTRAR : str
        Registro do cliente no servidor (login com nome de usuário, sem autenticação por senha).
    SAIR : str
        Desconexão do cliente do servidor
    NOTIFICACAO : str
        Mensagem assíncrona enviada pelo servidor ao cliente (sem resposta esperada)
    """

    ENVIAR_MENSAGEM = "enviar_mensagem"
    MENSAGEM_PRIVADA = "mensagem_privada"
    LISTAR_USUARIOS = "listar_usuarios"
    ENTRAR = "entrar"
    SAIR = "sair"
    NOTIFICACAO = "notificacao"


# Modos de Comunicação - R/RR/RRA
class ModoComuicacao:
    """
    Constantes que representam os estilos de comunicação suportados pelo protocolo.

    Attributes
    ----------
    R : str
        Request - cliente envia e não aguarda resposta
    RR : str
        Request-Reply - cliente envia e aguarda resposta do servidor
    RRA : str
        Request-Reply-ACK - cliente confirma o recebimento da mensagem após receber resposta
    """
    # DÍVIDA - talvez só fazer um dicionário ou até mesmo um enum
    # Serve para a classe anterior rs

    R = "R"
    RR = "RR"
    RRA = "RRA"


# Estruturas de mensageria
## Requisições, respostas, acks e afins 
def criar_requisicao(operacao_id, parametros = None, modo = ModoComuicacao.RR):
    """
    Cria um dicionário representando uma requisição RPC (Remote Process Call)

    Parameters
    ----------
    operacao_id : str
        Identificador da operação remota (ver a classe OperacaoId)
    parametros : dict
        Parâmetros da operação. Por padrão aqui é None
    modo : str
        Estilo de comunicação: "R", "RR" ou "RRA" (ver novamente a classe). Padrão é "RR".

    Returns
    -------
    dict
        Dicionário com os campos request_id, operacao_id, modo e parametros
    """
    if parametros is None:
        parametros = {}

    return {
        "request_id"  : str(uuid.uuid4()), # código da mensagem
        "operacao_id" : operacao_id,
        "modo"        : modo,
        "parametros"  : parametros,
    }


def criar_resposta(request_id, operacao_id, sucesso, dados = None, erro = None):
    """
    Cria um dicionário representando uma resposta RPC do servidor

    Parameters
    ----------
    request_id : str
        Identificador da REQUISIÇÃO original à qual esta resposta pertence
    operacao_id : str
        Identificador da OPERAÇÃO que gerou esta resposta
    sucesso : bool
        True se a operação foi executada com êxito e False caso contrário.
    dados : any
        Payload (conteúdo principal) de retorno em caso de sucesso. Padrão é None.
    erro : str
        Mensagem de erro em caso de falha. Padrão é None.

    Returns
    -------
    dict
        Dicionário com os campos
    """
    return {
        "request_id" : request_id,
        "operacao_id" : operacao_id,
        "sucesso" : sucesso,
        "dados" : dados,
        "erro" : erro,
    }


def criar_ack(request_id):
    """
    Cria um dicionário representando um ACK (confirmação de recebimento) do cliente
    Utilizado no modo de comunicação, logicamente, RRA após o cliente receber a resposta do servidor

    Parameters
    ----------
    request_id : str
        Identificador da requisição original sendo confirmada.

    Returns
    -------
    dict
        Dicionário
    """
    return {
        "tipo" : "ACK",
        "request_id" : request_id
    }


def criar_notificacao(conteudo):
    """
    Cria um dicionário representando uma notificação assíncrona do servidor
    Notificações são enviadas pelo servidor de forma unilateral, sem que o
    cliente tenha feito uma requisição prévia (ex.: novo usuário entrou no chat)

    Parameters
    ----------
    conteudo : str
        Texto a ser exibido no cliente

    Returns
    -------
    dict
        Dicionário 
    """
    return {
        "operacao_id": OperacaoId.NOTIFICACAO,
        "conteudo" : conteudo,
    }


# Banco de dados
## No caso aqui vamos trabalhar puramente com (des)serialização
def serializar(obj):
    """
    Serializa um dicionário de protocolo 

    Parameters
    ----------
    obj : dict
        Dicionário a ser serializado (requisição, resposta, ACK ou notificação)

    Returns
    -------
    bytes
        Representação .json do objeto codificada em UTF-8, terminada com ``\\n``

    """
    # o objetivo é colocar o objeto num json e decodificar a mensagem
    return (json.dumps(obj) + "\n").encode("utf-8")


def deserializar(dados_bytes):
    """
    Desserializa bytes recebidos da rede para um dicionário de protocolo (processo inverso) 

    Parameters
    ----------
    dados_bytes : bytes
        Bytes recebidos do socket, esperados no formato .json UTF-8

    Returns
    -------
    dict
        Dicionário reconstruído a partir do JSON.

    Raises
    ------
    json.JSONDecodeError
        Se os bytes não representarem um JSON válido.
    """
    # carrega o json
    return json.loads(dados_bytes.decode("utf-8").strip())