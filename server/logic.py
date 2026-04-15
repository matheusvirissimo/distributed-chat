"""
Camada de lógica de negócio do servidor de chat distribuído

Considerado como "cerébro" do chat. 
Gerencia o estado global do chat: usuários conectados, broadcast (transmissão),
unicast e notificações de entrada/saída
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..")) # pra ter acesso ao resto - ajuda com IA

from threading import Lock
from utils.protocol import criar_notificacao, serializar


class LogicaChat:
    """
    Lógica central do servidor de chat (servidor Remote Procedure Call - RPC)

    Mantém o dicionário de clientes ativos e expõe métodos que são invocados
    pelo dispatcher (no nosso caso, "despachador") ao receber requisições dos
    clientes. Todos os acessos ao estado compartilhado são protegidos por um
    threading.Lock.

    Attributes
    ----------
    _clientes : dict[str, Dispatcher]
        Mapeamento nome_usuario -> dispatcher dos clientes conectados
    _lock : threading.Lock
        Lock que protege _clientes contra condições de "corrida"
    """

    def __init__(self):
        self._clientes: dict = {}
        self._lock = Lock()

    # Operações remotas (invocadas pelo Dispatcher)
    def entrar(self, nome, dispatcher):
        """
        Registra um novo usuário no sistema de chat
        Esse usuário deve ter um nome diferente de algum já registrado (não que FOI registrado)

        Parameters
        ----------
        nome : str
            Nome de usuário desejado (deve ser único e não vazio)
        dispatcher : Dispatcher
            Objeto dispatcher associado ao socket do cliente

        Returns
        -------
        tuple[bool, str]
            (True, mensagem_boas_vindas) em caso de sucesso ou
            (False, mensagem_erro) se o nome for inválido/duplicado
        """
        if not nome:
            return False, "Nome de usuário não pode ser vazio."

        with self._lock:
            if nome in self._clientes:
                return False, f"O nome '{nome}' já está em uso. Escolha outro."

            self._clientes[nome] = dispatcher

        print(f"[LogicaChat] '{nome}' entrou no chat. Total: {len(self._clientes)}")
        self._broadcast(
            f">>> {nome} entrou no chat.",
            excluir=nome,
        )

        boas_vindas = (
            f"Bem-vindo, {nome}!\n"
            "Comandos disponíveis:\n"
            "  /p <usuario> <msg>  — mensagem privada\n"
            "  /list               — listar usuários conectados\n"
            "  /sair               — encerrar sessão\n"
            "  <mensagem>          — broadcast para todos"
        )
        return True, boas_vindas

    def enviar_mensagem(self, remetente, texto):
        """
        Faz o broadcast de uma mensagem para todos os usuários conectados

        Parameters
        ----------
        remetente : str
            Nome do usuário que enviou a mensagem
        texto : str
            Conteúdo da mensagem

        Returns
        -------
        tuple[bool, str]
            (True, "Mensagem enviada.") sempre que o remetente existe
            (False, mensagem_erro) se o remetente não estiver registrado
        """
        if not remetente or remetente not in self._clientes:
            return False, "Remetente não encontrado no sistema."

        conteudo = f"[{remetente}] {texto}"
        print(f"[Broadcast] {conteudo}")
        self._broadcast(conteudo, excluir=None)
        return True, "Mensagem enviada."

    def mensagem_privada(self, remetente, destino, texto):
        """
        Envia uma mensagem privada (unicast) de um usuário para outro

        Parameters
        ----------
        remetente : str
            Nome do usuário que envia a mensagem
        destino : str
            Nome do usuário destinatário
        texto : str
            Conteúdo da mensagem privada

        Returns
        -------
        tuple[bool, str]
            (True, confirmação) se o envio foi bem-sucedido
            (False, mensagem_erro) se o destinatário não existir
        """
        with self._lock:
            dispatcher_destino = self._clientes.get(destino)

        if dispatcher_destino is None:
            return False, f"Usuário '{destino}' não encontrado."

        conteudo = f"[Privado de {remetente}] {texto}"
        dispatcher_destino.enviar_notificacao(conteudo)
        print(f"[Unicast] {remetente} → {destino}: {texto}")
        return True, f"Mensagem privada enviada para '{destino}'."

    def listar_usuarios(self):
        """
        Retorna a lista de nomes dos usuários atualmente conectados

        Returns
        -------
        list[str]
            Lista com os nomes de todos os usuários conectados
        """
        with self._lock:
            return list(self._clientes.keys())

    def remover_usuario(self, nome):
        """
        Remove um usuário do registro e notifica os demais da saída

        Parameters
        ----------
        nome : str
            Nome do usuário a ser removido.
        """
        with self._lock:
            if nome not in self._clientes:
                return
            del self._clientes[nome]

        print(f"[LogicaChat] '{nome}' saiu. Total: {len(self._clientes)}")
        self._broadcast(f">>> {nome} saiu do chat.", excluir=None)

    # Utilitários internos - funções auxiliares
    def _broadcast(self, conteudo, excluir = None):
        """
        Envia uma notificação para todos os clientes conectados (como evento do sistema)

        Parameters
        ----------
        conteudo : str
            Texto a ser enviado como notificação
        excluir : str or None
            Nome do usuário que deve ser ignorado no envio (ex: o próprio remetente) 
            Se ``None``, envia para todos
        """
        with self._lock:
            alvos = list(self._clientes.items())

        mensagem_bytes = serializar(criar_notificacao(conteudo))

        for nome, dispatcher in alvos:
            if nome == excluir:
                continue
            try:
                dispatcher.socket_cliente.sendall(mensagem_bytes)
            except Exception as e:
                print(f"[Broadcast] Falha ao enviar para '{nome}': {e}")