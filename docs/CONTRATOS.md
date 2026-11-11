# Contratos de integração

## Registro dos módulos

Cada módulo fica em `app/modulos/<nome>/` e pode expor uma função
`registrar(container)` no seu `__init__.py`. A inicialização descobre os pacotes
automaticamente e chama essa função quando existir; não é necessário alterar
`app/main.py` para integrar um módulo.

O container disponibiliza:

- `engine`: engine SQLAlchemy compartilhada.
- `sessoes`: fábrica de sessões SQLAlchemy.
- `barramento`: barramento interno de eventos.
- `passageiros`: serviço que implementa `obter_identificador(nome, documento) -> int`.

Até a implementação definitiva de Passageiros, `passageiros` usa
`PassageiroFalso`. O módulo Passageiros deve registrá-lo com
`container.registrar_passageiros(servico)`. Reservas deve consultar
`container.passageiros` ao criar cada reserva, e não guardar o serviço no
momento do registro.

Reservas é o único módulo autorizado a chamar diretamente Passageiros, somente
para obter o identificador do passageiro. Os demais módulos se comunicam por
eventos. Cada módulo é responsável por suas tabelas; não crie chaves
estrangeiras entre tabelas de módulos diferentes.

## Barramento

Inscreva um tratador com `container.barramento.inscrever(TipoDoEvento, tratador)`
e publique com `container.barramento.publicar(evento)`. O tratador recebe a
instância do evento. Eventos publicados durante o tratamento são entregues
depois que o evento atual terminar. Erros dos tratadores são propagados ao
publicador.

## Eventos

Os eventos são dataclasses imutáveis definidos em `app/eventos.py`.

| Evento | Campos | Publicador | Consumidores previstos |
|---|---|---|---|
| `ReservaCriada` | `reserva_id: int`, `voo_id: int`, `codigo_assento: str`, `passageiro_id: int`, `valor: Decimal` | Reservas | Voos, Pagamentos, Notificações, Saga |
| `AssentoBloqueado` | `reserva_id: int`, `voo_id: int`, `codigo_assento: str` | Voos | Pagamentos |
| `AssentoIndisponivel` | `reserva_id: int`, `voo_id: int`, `codigo_assento: str`, `motivo: str` | Voos | Reservas, Saga |
| `PagamentoAprovado` | `reserva_id: int`, `pagamento_id: int`, `valor: Decimal` | Pagamentos | Reservas |
| `PagamentoRecusado` | `reserva_id: int`, `motivo: str` | Pagamentos | Saga |
| `ReservaConfirmada` | `reserva_id: int` | Reservas | Notificações, Saga |
| `LiberarAssento` | `reserva_id: int`, `voo_id: int`, `codigo_assento: str` | Saga | Voos |
| `CancelarReserva` | `reserva_id: int`, `motivo: str` | Saga | Reservas |
| `ReservaCancelada` | `reserva_id: int`, `motivo: str` | Reservas | Notificações |

Os consumidores previstos indicam a integração esperada; cada módulo deve
inscrever apenas os eventos que processa.
