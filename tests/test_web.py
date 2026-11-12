def test_pagina_inicial_e_servida(sistema):
    s = sistema("voos", "reservas")

    resposta = s.client.get("/")

    assert resposta.status_code == 200
    assert resposta.headers["content-type"].startswith("text/html")
    assert "ELVoo" in resposta.text
