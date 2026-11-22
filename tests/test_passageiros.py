from app.contratos import DadosPassageiro


def test_mesmo_documento_retorna_o_mesmo_id(sistema):
    s = sistema("passageiros")
    servico = s.container.passageiros

    primeiro = servico.criar_ou_validar(
        DadosPassageiro("Ana Souza", "12345", "ana@exemplo.com")
    )
    segundo = servico.criar_ou_validar(
        DadosPassageiro("Ana Costa", "12345", "outro@exemplo.com")
    )

    assert primeiro == segundo


def test_documentos_diferentes_criam_passageiros_diferentes(sistema):
    s = sistema("passageiros")
    servico = s.container.passageiros

    ana = servico.criar_ou_validar(
        DadosPassageiro("Ana Souza", "12345", "ana@exemplo.com")
    )
    bruno = servico.criar_ou_validar(
        DadosPassageiro("Bruno Lima", "67890", "bruno@exemplo.com")
    )

    assert ana != bruno


def test_documento_vazio_e_rejeitado(sistema):
    s = sistema("passageiros")
    servico = s.container.passageiros

    try:
        servico.criar_ou_validar(
            DadosPassageiro("Ana Souza", "   ", "ana@exemplo.com")
        )
    except ValueError as erro:
        assert "documento" in str(erro)
    else:
        raise AssertionError("Um documento vazio deveria gerar ValueError")
