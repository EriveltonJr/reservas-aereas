# Contratos de integração

## Registro dos módulos

Cada módulo fica em `app/modulos/<nome>/` e expõe no `__init__.py` a função
`registrar(app, bus, container)`. `app.main.criar_app(url=None, modulos=None)`
descobre os pacotes automaticamente, chama `registrar` quando existir e cria as
tabelas. Para subir a API: `uvicorn app.main:criar_app --factory`.

- `app`: aplicação FastAPI, onde o módulo inclui o seu router.
- `bus`: barramento interno de eventos.
- `container`: expõe `engine`, `bus`, `passageiros` e `autenticacao`.

O acesso ao banco é feito com `with sessao():` de `app.banco`. Eventos são
publicados sempre depois de sair do bloco `with sessao()`, quando o commit já
aconteceu. Datas são gravadas em UTC (`app.banco.agora()`).

Cada módulo é responsável por suas tabelas, que começam com o nome do módulo
(`voos_...`, `reservas_...`). Não existe chave estrangeira entre módulos.

As regras de negócio compartilhadas (prazo de pagamento, cancelamento gratuito,
antecedência mínima de compra e sessão) ficam em `app/politicas.py`.

## Contas e permissões

O módulo Contas registra o serviço de autenticação com
`container.registrar_autenticacao(servico)`. As rotas protegidas usam as
dependências de `app/seguranca.py`:

| Dependência | Uso |
|---|---|
| `usuario_opcional` | Usuário logado ou `None` |
| `exigir_usuario` | 401 sem login; devolve `UsuarioAutenticado(id, nome, email, papel)` |
| `exigir_admin` | 403 se o usuário não for `ADMIN` |

A sessão fica em um cookie `HttpOnly` e `SameSite=Strict`. Requisições que
alteram dados precisam do cabeçalho `X-Requested-With: fetch` (403 sem ele).

Não existe cadastro público de administrador. Para criar ou promover um:

```bash
python -m app.modulos.contas criar-admin email@dominio.com --nome "Nome"
```

## Passageiros

A única chamada direta entre módulos é:

```python
container.passageiros.criar_ou_validar(DadosPassageiro(nome, documento, email))  # -> int
```

O mesmo documento sempre devolve o mesmo id. Reservas guarda só o
`passageiro_id`, nunca nome, documento ou email.

## Eventos

Os eventos são dataclasses imutáveis definidos em `app/eventos.py`.

| Evento | Campos | Publicador | Consumidores |
|---|---|---|---|
| `ReservaCriada` | `reserva_id`, `voo_id`, `assento`, `passageiro_id`, `conta_id`, `localizador` | Reservas | Voos, Pagamentos, Notificações |
| `AssentoBloqueado` | `reserva_id`, `voo_id`, `assento`, `valor` | Voos | Pagamentos |
| `AssentoIndisponivel` | `reserva_id`, `motivo` | Voos | Saga |
| `PagamentoAprovado` | `reserva_id`, `pagamento_id`, `valor` | Pagamentos | Reservas |
| `PagamentoRecusado` | `reserva_id`, `motivo` | Pagamentos | Notificações |
| `PrazoPagamentoExpirado` | `reserva_id` | Pagamentos | Saga |
| `PagamentoEstornado` | `reserva_id`, `pagamento_id`, `valor` | Pagamentos | Notificações |
| `ReservaConfirmada` | `reserva_id`, `passageiro_id`, `valor`, `conta_id`, `localizador` | Reservas | Notificações |
| `CancelamentoSolicitado` | `reserva_id`, `motivo` | Reservas | Saga |
| `LiberarAssento` | `reserva_id` | Saga | Voos |
| `CancelarReserva` | `reserva_id`, `motivo` | Saga | Reservas |
| `ReservaCancelada` | `reserva_id`, `passageiro_id`, `motivo`, `conta_id`, `localizador` | Reservas | Pagamentos, Notificações |

`PagamentoRecusado` representa uma tentativa recusada: a reserva continua
aguardando pagamento até o prazo acabar. Quem desfaz a reserva é a Saga, ao
receber `AssentoIndisponivel`, `PrazoPagamentoExpirado` ou
`CancelamentoSolicitado`.

Cada módulo trata os próprios erros dentro dos seus tratadores de eventos.

## Rotas

Erros: 401 sem login, 403 sem permissão, 404 quando não existe (ou não pertence
ao usuário), 409 quando repete ou a operação não é permitida, 422 quando a
entrada é inválida e 402 quando o cartão é recusado.

### Contas

| Método | Rota | Acesso | Resposta |
|---|---|---|---|
| `POST` | `/auth/cadastro` | público | 201 e sessão iniciada; 409 se o e-mail já existe |
| `POST` | `/auth/entrar` | público | 200 e sessão iniciada; 401 credenciais inválidas; 429 após tentativas seguidas |
| `POST` | `/auth/sair` | público | 204 |
| `GET` | `/auth/eu` | cliente | dados da conta |

### Voos

| Método | Rota | Acesso | Resposta |
|---|---|---|---|
| `GET` | `/voos` | público | voos à venda com `assentos_livres` (`incluir_encerrados=true` para o admin) |
| `GET` | `/voos/{voo_id}` | público | voo com `assentos` e `vendas_abertas` |
| `POST` | `/voos` | admin | 201; 409 se o código já existe |
| `PATCH` | `/voos/{voo_id}` | admin | altera o `preco` (vale para novas reservas) |

Corpo do `POST /voos`: `codigo`, `origem`, `destino`, `preco`, `partida` e
`chegada` (data e hora com fuso) e `assentos` (1 a 300, formato `12A`).

### Reservas

| Método | Rota | Acesso | Resposta |
|---|---|---|---|
| `POST` | `/reservas` | cliente | 201 com a reserva `PENDENTE`, `localizador` e `prazo_pagamento` |
| `GET` | `/reservas` | cliente | reservas da conta (todas, para o admin) |
| `GET` | `/reservas/{reserva_id}` | cliente | reserva; 404 se não existe ou é de outra conta |
| `POST` | `/reservas/{reserva_id}/cancelar` | cliente | cancela conforme a política; 409 fora do prazo |

### Pagamentos

| Método | Rota | Acesso | Resposta |
|---|---|---|---|
| `POST` | `/pagamentos/{reserva_id}` | cliente | paga com `titular`, `numero`, `validade` (MM/AA) e `cvv`; 402 recusado; 409 prazo expirado ou já pago |
| `GET` | `/pagamentos/{reserva_id}` | cliente | cobrança e tentativas |
| `GET` | `/pagamentos` | admin | todas as cobranças |

Do cartão, só a bandeira e os 4 últimos dígitos são armazenados.

### Notificações

| Método | Rota | Acesso | Resposta |
|---|---|---|---|
| `GET` | `/notificacoes` | cliente | `{nao_lidas, itens}` da conta (avisos operacionais, para o admin) |
| `POST` | `/notificacoes/{id}/lida` | cliente | 204 |
| `POST` | `/notificacoes/lidas` | cliente | 204 |
