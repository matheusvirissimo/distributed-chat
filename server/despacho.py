"""
Dispatcher (Skeleton) do servidor de chat distribuído com RPC/RMI.

Responsável por:
- Receber requisições JSON de cada cliente via socket.
- Identificar a operação solicitada (OperationId).
- Delegar a execução ao método correto da camada de lógica.
- Enviar a resposta ao cliente (e, no modo RRA, aguardar o ACK).
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.protocol import (
    OperacaoId,
    ModoComuicacao,
    criar_resposta,
    criar_notificacao,
    serializar,
    deserializar,
)


class Dispatcher:
    """
    Dispatcher RPC do lado servidor

    Recebe requisições brutas de um socket de cliente, identifica a operação
    pelo campo operacao_id e delega a execução ao objeto correto.
    Ele nada mais é do que um "conector", que faz a ligação entre o socket 
    do cliente e a lógica do chat. 

    Parameters
    ----------
    logica : LogicaChat
        Instância da lógica do chat a ser chamada
    socket_cliente : socket.socket
        Socket TCP conectado ao cliente
    nome_cliente : str
        Nome do usuário associado a este dispatcher (preenchido após "login").

    Attributes
    ----------
    logica : LogicaChat
        Responsável pela "gerência" do processo
    socket_cliente : socket.socket
    nome_cliente : str
    _buffer : str
        Acumulador de fragmentos de mensagens recebidos via TCP
    """

    def __init__(self, logica, socket_cliente, nome_cliente=""):
        self.logica = logica
        self.socket_cliente = socket_cliente
        self.nome_cliente = nome_cliente
        self._buffer = "" #iniciar vázio

    # Recepção de mensagens (getRequest)
    def receber_requisicao(self):
        """
        Aguarda e lê uma requisição completa (delimitada por \n) do socket
        usa um buffer interno para lidar com fragmentação TCP

        Returns
        -------
        dict or None
            Dicionário da requisição recebida, ou None se a conexão foi encerrada pelo cliente.

        Raises
        ------
        ConnectionError
            Se ocorrer erro na leitura do socket
        """
        while "\n" not in self._buffer:
            fragmento = self.socket_cliente.recv(4096).decode("utf-8")
            if not fragmento:
                return None
            self._buffer += fragmento

        linha, self._buffer = self._buffer.split("\n", 1)
        return deserializar(linha.encode("utf-8"))

    # Envio de resposta (sendReply)
    def enviar_resposta(self, resposta):
        """
        Serializa e envia uma resposta ao cliente conectado

        Parameters
        ----------
        resposta : dict
            Dicionário de resposta criado por 
        """
        self.socket_cliente.sendall(serializar(resposta))

    def enviar_notificacao(self, conteudo):
        """
        Envia uma notificação assíncrona (push) ao cliente
        Importante citar que as notificações não estão vinculadas a nenhuma requisição específica e
        são usadas para eventos do sistema (ex: usuário entrou/saiu)

        Parameters
        ----------
        conteudo : str
            Texto da notificação
        """
        try:
            self.socket_cliente.sendall(serializar(criar_notificacao(conteudo)))
        except Exception:
            pass

    # Loop principal de despacho (doOperation -> lado servidor)
    def processar(self):
        """
        Executa enquanto o cliente estiver conectado:

        1. Lê a próxima requisição (getRequest)
        2. Identifica a operação e chama o método correspondente da camada de lógica
        3. Monta e envia a resposta (sendReply)
        4. Se o modo for RRA, aguarda o ACK do cliente
        5. Encerra quando o cliente envia OperacaoId.SAIR ou desconecta

        O mapeamento de operações segue o padrão de tabela de despacho
        (dispatch table), evitando cadeias de if/elif.
        """
        tabela = {
            OperacaoId.ENTRAR : self._despachar_entrar,
            OperacaoId.ENVIAR_MENSAGEM : self._despachar_enviar_mensagem,
            OperacaoId.MENSAGEM_PRIVADA : self._despachar_mensagem_privada,
            OperacaoId.LISTAR_USUARIOS : self._despachar_listar_usuarios,
            OperacaoId.SAIR : self._despachar_sair,
        }

        try:
            while True:
                requisicao = self.receber_requisicao()

                if requisicao is None:
                    # Cliente fechou a conexão abruptamente
                    print(f"[Dispatcher] {self.nome_cliente or '?'} desconectou sem enviar FIM.")
                    break

                operacao = requisicao.get("operacao_id")
                modo = requisicao.get("modo", ModoComuicacao.RR)
                handler = tabela.get(operacao)

                if handler is None:
                    resposta = criar_resposta(
                        requisicao["request_id"], operacao,
                        sucesso = False, erro = f"Operação desconhecida: {operacao}"
                    )
                    self.enviar_resposta(resposta)
                    continue

                # executa a operação
                resposta = handler(requisicao)

                # R: sem resposta
                if modo == ModoComuicacao.R:
                    pass

                # RR ou RRA: envia resposta
                else:
                    self.enviar_resposta(resposta)

                    # RRA: aguarda confirmação do cliente
                    if modo == ModoComuicacao.RRA:
                        self._aguardar_ack(requisicao["request_id"])

                # Encerra o loop
                if operacao == OperacaoId.SAIR:
                    break

        finally:
            self._encerrar()

    # Handlers individuais de operação
    def _despachar_entrar(self, requisicao):
        """
        Processa a operação de entrada (login) de um novo usuário
        Não é feito nenhuma verificação por senha, apenas verifica se o nome já 
        está sendo previamente usado

        Parameters
        ----------
        requisicao : dict
            Requisição com parametros["nome"] contendo o nome desejado

        Returns
        -------
        dict
            Resposta indicando sucesso ou falha no registro do usuário
        """
        nome = requisicao["parametros"].get("nome", "").strip()
        ok, mensagem = self.logica.entrar(nome, self)

        if ok:
            self.nome_cliente = nome

        return criar_resposta(
            requisicao["request_id"], OperacaoId.ENTRAR,
            sucesso = ok,
            dados = mensagem if ok else None,
            erro = mensagem if not ok else None,
        )

    def _despachar_enviar_mensagem(self, requisicao):
        """
        Processa a operação de transmissão da mensagem

        Parameters
        ----------
        requisicao : dict
            Requisição com parametros["mensagem"] contendo o texto

        Returns
        -------
        dict
            Resposta confirmando o envio ou indicando o erro
        """
        texto = requisicao["parametros"].get("mensagem", "")
        ok, info = self.logica.enviar_mensagem(self.nome_cliente, texto)

        return criar_resposta(
            requisicao["request_id"], OperacaoId.ENVIAR_MENSAGEM,
            sucesso = ok,
            dados = info if ok else None,
            erro = info if not ok else None,
        )

    def _despachar_mensagem_privada(self, requisicao):
        """
        Processa a operação de mensagem privada (unicast, só um lado recebe)

        Parameters
        ----------
        requisicao : dict
            Requisição com parametros["destino"] e parametros["mensagem"]

        Returns
        -------
        dict
            Resposta confirmando o envio ou indicando usuário não encontrado
        """
        destino = requisicao["parametros"].get("destino", "")
        texto = requisicao["parametros"].get("mensagem", "")
        ok, info = self.logica.mensagem_privada(self.nome_cliente, destino, texto)

        return criar_resposta(
            requisicao["request_id"], OperacaoId.MENSAGEM_PRIVADA,
            sucesso = ok,
            dados = info if ok else None,
            erro = info if not ok else None,
        )

    def _despachar_listar_usuarios(self, requisicao):
        """
        Operação de listagem de usuários conectados

        Parameters
        ----------
        requisicao : dict
            Requisição (sem parâmetros adicionais necessários).

        Returns
        -------
        dict
            Resposta com dados["usuarios"] contendo a lista de nomes
        """
        usuarios = self.logica.listar_usuarios()

        return criar_resposta(
            requisicao["request_id"], OperacaoId.LISTAR_USUARIOS,
            sucesso=True,
            dados={"usuarios": usuarios},
        )

    def _despachar_sair(self, requisicao):
        """
        Saída do cliente.

        Parameters
        ----------
        requisicao : dict
            Requisição de encerramento da sessão

        Returns
        -------
        dict
            Resposta confirmando o encerramento
        """
        return criar_resposta(
            requisicao["request_id"], OperacaoId.SAIR,
            sucesso=True,
            dados="Sessão encerrada. Até logo!",
        )

    # ACK (modo RRA)
    ## Confirma recebimento da mensagem (TCP)
    def _aguardar_ack(self, request_id_esperado):
        """
        Aguarda o ACK do cliente para uma requisição específica

        Lê a próxima mensagem do buffer. Se for um ACK válido com o
        request_id correto, registra a confirmação. 
        Caso contrário, registra aviso mas não bloqueia o processamento.

        Parameters
        ----------
        request_id_esperado : str
            Código (UUID) da requisição cujo ACK deve ser recebido
        """
        try:
            msg = self.receber_requisicao()
            if msg and msg.get("tipo") == "ACK":
                if msg.get("request_id") == request_id_esperado:
                    print(f"[RRA] ACK recebido de '{self.nome_cliente}' para req {request_id_esperado[:8]}…")
                else:
                    print(f"[RRA] ACK com request_id inesperado de '{self.nome_cliente}'.")
        except Exception as e:
            print(f"[RRA] Erro ao aguardar ACK: {e}")

    # Encerramento
    def _encerrar(self):
        """
        Realiza a limpeza de recursos ao final da sessão do cliente

        Remove o usuário do registro global, notifica os demais clientes e fecha o socket
        [EVENTO DO SISTEMA]
        """
        if self.nome_cliente:
            self.logica.remover_usuario(self.nome_cliente)
            print(f"[Dispatcher] '{self.nome_cliente}' removido do sistema.")

        try:
            self.socket_cliente.close()
        except Exception:
            pass