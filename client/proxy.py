"""
Proxy (Stub) do cliente para o sistema de chat distribuído com RPC/RMI.
* Peça mais importante de todo o conceito de RPC, pois é ele o responsável por 
enganar o código fazendo tudo parecer local.

Simula chamadas locais que, internamente, são transformadas em requisições
remotas JSON enviadas ao servidor via TCP, implementando o padrão de Proxy
do modelo RPC/RMI. Para o usuário, dá a impressão de ser tudo local. 

Exemplo: 
    chat = ProxyChat(socket)
    chat.enviar_mensagem("Olá a todos!") <---- parece local, mas é remoto pois envia a toda rede
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.protocol import (
    OperacaoId,
    ModoComuicacao,
    criar_requisicao,
    criar_ack,
    serializar,
    deserializar,
)


class ProxyChat:
    """
    Proxy (Stub) do lado cliente - camada de abstração RPC.

    Cada método público desta classe corresponde a uma operação remota do
    servidor. Internamente, o proxy:

    1. Serializa os parâmetros em uma requisição JSON com request_id (UUID) único
    2. Envia a requisição ao servidor via socket TCP
    3. Aguarda a resposta (modo RR(Request-Reply)/RRA(Request-Reply-ACK)) ou apenas envia (modo R(Request))
    4. No modo RRA, envia um ACK após receber a resposta
    5. Retorna o resultado ao chamador como se fosse uma chamada local

    Parameters
    ----------
    socket_cliente : socket.socket
        Socket TCP JÁ conectado ao servidor

    Attributes
    ----------
    socket_cliente : socket.socket
    _buffer : str
        Acumulador de fragmentos TCP para garantir leitura de mensagens completas
    """

    def __init__(self, socket_cliente):
        self.socket_cliente = socket_cliente
        self._buffer = ""

    # Operações remotas (de forma a parecerem chamadas locais)
    def entrar(self, nome):
        """
        Invoca remotamente a operação de entrada no chat (login).

        Usa o modo RR: aguarda confirmação do servidor.

        Parameters
        ----------
        nome : str
            Nome de usuário desejado.

        Returns
        -------
        tuple[bool, str]
            (True, mensagem_boas_vindas) em caso de sucesso ou
            (False, mensagem_erro) se o nome já estiver em uso
        """
        resposta = self._do_operation(
            operacao_id = OperacaoId.ENTRAR,
            parametros = {"nome": nome},
            modo = ModoComuicacao.RR,
        )
        return resposta["sucesso"], resposta.get("dados") or resposta.get("erro", "")

    def enviar_mensagem(self, mensagem):
        """
        Invoca remotamente o broadcast de uma mensagem para todos os clientes.

        Usa o modo "R": envia e não aguarda resposta

        Parameters
        ----------
        mensagem : str
            Mensagem a ser enviada por chat
        """
        self._do_operation(
            operacao_id = OperacaoId.ENVIAR_MENSAGEM,
            parametros = {"mensagem": mensagem},
            modo = ModoComuicacao.R,
        )

    def mensagem_privada(self, destino, mensagem):
        """
        Invoca remotamente o envio de uma mensagem privada
        usando o modo *RRA* (Request-Reply-Ack): envia, aguarda resposta e
        confirma o recebimento com um ACK.

        Parameters
        ----------
        destino : str
            Nome do usuário destinatário.
        mensagem : str
            Texto da mensagem privada.

        Returns
        -------
        tuple[bool, str]
            ``(True, confirmação)`` ou ``(False, erro)`` retornado pelo servidor.
        """
        resposta = self._do_operation(
            operacao_id = OperacaoId.MENSAGEM_PRIVADA,
            parametros = {"destino": destino, "mensagem": mensagem},
            modo = ModoComuicacao.RRA,
        )
        return resposta["sucesso"], resposta.get("dados") or resposta.get("erro", "")

    def listar_usuarios(self):
        """
        Faz a listagem remotamente de usuários conectados (saber quem está online, para mandar mensagem priv.).
        Usa o modo *RR* (Request-Reply).

        Returns
        -------
        list[str] | List[None]
            Lista de nomes dos usuários conectados OU lista vazia em caso de erro
        """
        resposta = self._do_operation(
            operacao_id = OperacaoId.LISTAR_USUARIOS,
            parametros = {},
            modo = ModoComuicacao.RR,
        )
        if resposta["sucesso"]:
            return resposta["dados"].get("usuarios", [])
        return []

    def sair(self):
        """
        Operação de saída do chat
        Usa o modo **RR** (Requisição-resposta)

        Returns
        -------
        str
            Mensagem de finalização do chat
        """
        resposta = self._do_operation(
            operacao_id = OperacaoId.SAIR,
            parametros = {},
            modo = ModoComuicacao.RR,
        )
        return resposta.get("dados", "Sessão encerrada.")

    # Motor de invocação remota (doOperation)

    def _do_operation(self, operacao_id, parametros, modo):
        """
        Implementação do protocolo de invocação remota (doOperation)
        Empacota os parâmetros, envia ao servidor e, conforme o modo de
        comunicação usado, aguarda e processa a resposta.

        Parameters
        ----------
        operacao_id : str
            Identificador da operação a ser invocada no servidor
        parametros : dict
            Argumentos da operação.
        modo : str
            Modo de comunicação: "R", "RR" ou "RRA"

        Returns
        -------
        dict
            Dicionário de resposta recebido do servidor. Importante citar que
            Para o modo "R", retornará um dicionário de sucesso "falso" (entenda por sintético)

        Raises
        ------
        ConnectionError
            Se a conexão com o servidor for perdida durante a invocação ou f
        """
        requisicao = criar_requisicao(operacao_id, parametros, modo)
        self.socket_cliente.sendall(serializar(requisicao))

        # Modo R: sem espera de resposta
        if modo == ModoComuicacao.R:
            return {"sucesso": True, "dados": None, "erro": None}

        # Modos RR e RRA: aguarda resposta
        resposta = self._receber_resposta()

        # Modo RRA: envia ACK ao servidor
        if modo == ModoComuicacao.RRA:
            ack = criar_ack(requisicao["request_id"])
            self.socket_cliente.sendall(serializar(ack))

        return resposta

    def _receber_resposta(self):
        """
        Leitura do socket a próxima mensagem de resposta do servidor

        Usa um buffer interno para lidar com fragmentação TCP, filtrando
        notificações assíncronas recebidas enquanto aguarda a resposta
        de uma requisição específica.

        Returns
        -------
        dict
            Resposta recebida.

        Raises
        ------
        ConnectionError
            Se o servidor fechar a conexão inesperadamente.
        """
        while True:
            while "\n" not in self._buffer:
                fragmento = self.socket_cliente.recv(4096).decode("utf-8")
                if not fragmento:
                    raise ConnectionError("Conexão com o servidor encerrada.")
                self._buffer += fragmento

            linha, self._buffer = self._buffer.split("\n", 1)
            msg = deserializar(linha.encode("utf-8"))

            # Notificações assíncronas chegam enquanto aguardamos -> exibe e ignora
            if msg.get("operacao_id") == "notificacao":
                print(f"\n  [Sistema] {msg['conteudo']}")
                continue

            return msg