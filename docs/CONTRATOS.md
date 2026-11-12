# Contratos de integração

## Registro dos módulos

Cada módulo fica em `app/modulos/<nome>/` e expõe no `__init__.py` a função
`registrar(app, bus, container)`. `app.main.criar_app(url=None, modulos=None)`
descobre os pacotes automaticamente, chama `registrar` quando existir e cria as
tabelas. Para subir a API: `uvicorn app.main:criar_app --factory`.

- `app`: aplicação FastAPI, onde o módulo inclui o seu router.
- `bus`: barramento interno de eventos.
- `container`: expõe `engine`, `bus` e `passageiros`.

O acesso ao banco é feito com `with sessao():` de `app.banco`. Eventos são
publicados sempre depois de sair do bloco `with sessao()`, quando o commit já
aconteceu.

Cada módulo é responsável por suas tabelas, que começam com o nome do módulo
(`voos_...`, `reservas_...`). Não existe chave estrangeira entre módulos.

## Passageiros

A única chamada direta entre módulos é:

```python
container.passageiros.criar_ou_validar(DadosPassageiro(nome, documento, email))  # -> int
```

`DadosPassageiro` fica em `app/contratos.py`. Até a implementação definitiva,
`container.passageiros` é um `PassageiroFalso`. O módulo Passageiros deve
registrar o seu serviço com `container.registrar_passageiros(servico)`.
Reservas guarda só o `passageiro_id`, nunca nome, documento ou email.

## Barramento

Inscreva um tratador com `bus.inscrever(TipoDoEvento, tratador)` e publique com
`bus.publicar(evento)`. Eventos publicados durante o tratamento são entregues
depois que o evento atual terminar. Erros dos tratadores são propagados ao
publicador.

## Eventos

Os eventos são dataclasses imutáveis definidos em `app/eventos.py`.

| Evento | Campos | Publicador | Consumidores |
|---|---|---|---|
| `ReservaCriada` | `reserva_id`, `voo_id`, `assento`, `passageiro_id` | Reservas | Voos |
| `AssentoBloqueado` | `reserva_id`, `voo_id`, `assento`, `valor` | Voos | Pagamentos |
| `AssentoIndisponivel` | `reserva_id`, `motivo` | Voos | Saga |
| `PagamentoAprovado` | `reserva_id`, `pagamento_id`, `valor` | Pagamentos | Reservas |
| `PagamentoRecusado` | `reserva_id`, `motivo` | Pagamentos | Saga |
| `ReservaConfirmada` | `reserva_id`, `passageiro_id`, `valor` | Reservas | Notificações |
| `LiberarAssento` | `reserva_id` | Saga | Voos |
| `CancelarReserva` | `reserva_id`, `motivo` | Saga | Reservas |
| `ReservaCancelada` | `reserva_id`, `passageiro_id`, `motivo` | Reservas | Notificações |

Qualquer módulo pode consumir outros eventos além dos listados, se precisar.

Voos responde a `ReservaCriada` com `AssentoBloqueado` ou `AssentoIndisponivel`
(motivos `"Voo ou assento inexistente"` ou `"Assento já ocupado"`).
`LiberarAssento` sem assento bloqueado não gera erro.

Cada módulo trata os próprios erros dentro dos seus tratadores de eventos.

## Rotas

Erros: 404 quando não existe, 409 quando repete, 422 quando a entrada é inválida.

### Voos

| Método | Rota | Resposta |
|---|---|---|
| `POST` | `/voos` | 201 com `id`, `codigo`, `origem`, `destino`, `preco`; 409 se o código já existe |
| `GET` | `/voos` | até 100 voos, cada um com `assentos_livres` |
| `GET` | `/voos/{voo_id}` | voo com `assentos: [{numero, status}]`; 404 se não existe |

Corpo do `POST /voos`: `codigo` (3 a 20 letras e números, salvo em maiúsculas),
`origem` e `destino` (3 a 50), `preco` (maior que 0 e até 100000) e `assentos`
(1 a 300, sem repetição, formato `12A`). Status dos assentos: `LIVRE` ou
`BLOQUEADO`.

### Reservas

| Método | Rota | Resposta |
|---|---|---|
| `POST` | `/reservas` | 201 com a reserva; publica `ReservaCriada` (status `PENDENTE` só enquanto Pagamentos e Saga não existirem) |
| `GET` | `/reservas/{reserva_id}` | reserva; 404 se não existe |

Corpo do `POST /reservas`: `voo_id` (maior que 0), `assento` (formato `12A`) e
`passageiro` com `nome` (2 a 120), `documento` (5 a 30, letras, números, ponto e
hífen) e `email` (até 120). A reserva devolvida tem `id`, `voo_id`, `assento`,
`passageiro_id`, `status` (`PENDENTE`, `CONFIRMADA` ou `CANCELADA`), `valor` e
`motivo_cancelamento`.

## Módulos do Liedson

O que está abaixo é o mínimo para os módulos se encaixarem no sistema. Tabelas,
colunas, rotas, mensagens e a organização interna de cada módulo ficam a
critério de quem implementa.

| Módulo | Precisa fazer |
|---|---|
| Passageiros | Registrar um serviço com `criar_ou_validar(DadosPassageiro) -> int` via `container.registrar_passageiros(servico)`. O mesmo documento deve sempre devolver o mesmo id. |
| Pagamentos | Consumir `AssentoBloqueado` e responder com `PagamentoAprovado` ou `PagamentoRecusado`. A regra que decide fica livre, desde que seja possível provocar uma recusa para demonstrar a compensação. |
| Saga | Ao receber `AssentoIndisponivel`, publicar `CancelarReserva`. Ao receber `PagamentoRecusado`, publicar `LiberarAssento` e `CancelarReserva`. |
| Notificações | Reagir a `ReservaConfirmada` e `ReservaCancelada` avisando o passageiro, mesmo que de forma simulada (registro, log...). |

Notificações recebe só o `passageiro_id`. Pelas regras do projeto, a única
chamada direta entre módulos é Reservas → Passageiros, então os avisos podem ser
registrados pelo `passageiro_id`.
