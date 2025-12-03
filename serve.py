# -*- coding: utf-8 -*-
import threading
import socket
import sys

# Lista de clientes conectados ao servidor: armazenamos tuplas (socket, addr, username)
clients = []
clients_lock = threading.Lock()


# Função para listar usuários online (retorna lista de strings "IP:PORT")
def list_online():
    with clients_lock:
        out = []
        for (_sock, addr, username) in clients:
            if username:
                out.append(f"{username} ({addr[0]}:{addr[1]})")
            else:
                out.append(f"{addr[0]}:{addr[1]}")
        return out


# Função para remover um cliente da lista e fechar o socket
def remove_client(client_sock):
    with clients_lock:
        for entry in list(clients):
            sock, addr, username = entry
            if sock == client_sock:
                try:
                    sock.close()
                except:
                    pass
                try:
                    clients.remove(entry)
                except ValueError:
                    pass
                break


def set_username(client_sock, username):
    with clients_lock:
        for i, entry in enumerate(clients):
            sock, addr, _ = entry
            if sock == client_sock:
                clients[i] = (sock, addr, username)
                return True
    return False


def get_username(client_sock):
    with clients_lock:
        for sock, addr, username in clients:
            if sock == client_sock:
                return username
    return None


def find_sock_by_username(username):
    with clients_lock:
        for sock, addr, uname in clients:
            if uname == username:
                return sock
    return None


# Função para transmitir mensagens para todos os clientes
def broadcast_text(text, sender_sock=None):
    data = text.encode('utf-8')
    # snapshot para evitar problemas de iteração concorrente
    with clients_lock:
        snapshot = list(clients)

    for client_sock, addr, _username in snapshot:
        if client_sock != sender_sock:
            try:
                client_sock.send(data)
            except:
                remove_client(client_sock)


def send_text_to_sock(text, sock):
    try:
        sock.send(text.encode('utf-8'))
    except:
        remove_client(sock)


# Função para lidar com as mensagens de um cliente
def handle_client(client_sock, addr):
    while True:
        try:
            raw = client_sock.recv(2048)
            if not raw:
                remove_client(client_sock)
                break

            try:
                text = raw.decode('utf-8', errors='ignore').strip()
            except:
                text = ''

            # Registro de username: $username$
            if text.startswith('$') and text.endswith('$') and len(text) > 2:
                username = text[1:-1].strip()
                if username:
                    set_username(client_sock, username)
                    print(f'Usuário registrado: {username} - {addr}')
                    send_text_to_sock(f'Você está registrado como {username}', client_sock)
                continue

            sender = get_username(client_sock) or f'{addr[0]}:{addr[1]}'

            # Mensagem privada com /msg user message ou @user message
            if text.startswith('/msg ') or text.startswith('/MSG '):
                parts = text.split(' ', 2)
                if len(parts) >= 3:
                    _, target, message = parts
                    target_sock = find_sock_by_username(target)
                    if target_sock:
                        send_text_to_sock(f'(privado) <{sender}> {message}', target_sock)
                        send_text_to_sock(f'(para {target}) <{sender}> {message}', client_sock)
                    else:
                        send_text_to_sock(f'Usuário {target} não encontrado.', client_sock)
                else:
                    send_text_to_sock('Uso: /msg usuario mensagem', client_sock)
                continue

            if text.startswith('@'):
                # formato: @usuario mensagem
                parts = text.split(' ', 1)
                if len(parts) == 2:
                    target = parts[0][1:]
                    message = parts[1]
                    target_sock = find_sock_by_username(target)
                    if target_sock:
                        send_text_to_sock(f'(privado) <{sender}> {message}', target_sock)
                        send_text_to_sock(f'(para {target}) <{sender}> {message}', client_sock)
                    else:
                        send_text_to_sock(f'Usuário {target} não encontrado.', client_sock)
                else:
                    send_text_to_sock('Uso: @usuario mensagem', client_sock)
                continue

            # Mensagem pública: anexa remetente
            broadcast_text(f'<{sender}> {text}', sender_sock=client_sock)

        except:
            remove_client(client_sock)
            break


def server_console(server_sock):
    # Permite comandos simples no console do servidor: list, exit
    try:
        while True:
            cmd = input().strip().lower()
            if cmd == 'list':
                users = list_online()
                print('Usuários online:')
                for u in users:
                    print(' -', u)
                if not users:
                    print(' (nenhum)')
            elif cmd in ('quit', 'exit'):
                print('Encerrando servidor...')
                # fecha conexões
                with clients_lock:
                    for sock, _ in list(clients):
                        try:
                            sock.close()
                        except:
                            pass
                    clients.clear()
                try:
                    server_sock.close()
                except:
                    pass
                sys.exit(0)
    except (KeyboardInterrupt, EOFError):
        print('\nConsole do servidor finalizado.')


# Função principal
def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    print("Iniciou o servidor de bate-papo")

    try:
        server.bind(("0.0.0.0", 7777))
        server.listen()
    except Exception:
        return print('\nNão foi possível iniciar o servidor!\n')

    # Inicia thread para comandos no console do servidor
    console_thread = threading.Thread(target=server_console, args=(server,), daemon=True)
    console_thread.start()

    while True:
        try:
            client, addr = server.accept()
        except Exception:
            break

        with clients_lock:
            clients.append((client, addr))

        print(f'Cliente conectado com sucesso. IP: {addr}')

        # Inicia uma nova thread para lidar com as mensagens do cliente
        thread = threading.Thread(target=handle_client, args=(client, addr), daemon=True)
        thread.start()


if __name__ == '__main__':
    main()