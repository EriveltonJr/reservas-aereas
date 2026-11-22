"use strict";

/* ---------- Utilidades ---------- */

class Seguro {
  constructor(valor) { this.valor = valor; }
}
const seguro = (valor) => new Seguro(valor);
const ESCAPES = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
const escapar = (texto) => String(texto).replace(/[&<>"']/g, (c) => ESCAPES[c]);
const converter = (valor) => {
  if (valor instanceof Seguro) return valor.valor;
  if (Array.isArray(valor)) return valor.map(converter).join("");
  if (valor == null || valor === false) return "";
  return escapar(valor);
};
function html(partes, ...valores) {
  return seguro(partes.reduce((acc, parte, i) => acc + parte + (i < valores.length ? converter(valores[i]) : ""), ""));
}
const $ = (seletor, base = document) => base.querySelector(seletor);
const $$ = (seletor, base = document) => [...base.querySelectorAll(seletor)];
const icone = (id, tamanho = 18) => html`<svg width="${tamanho}" height="${tamanho}" aria-hidden="true"><use href="#${id}"/></svg>`;
const app = $("#app");
const montar = (conteudo) => { app.innerHTML = conteudo.valor; };

const moeda = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" });
const fmtDia = new Intl.DateTimeFormat("pt-BR", { weekday: "short", day: "2-digit", month: "short" });
const fmtHora = new Intl.DateTimeFormat("pt-BR", { hour: "2-digit", minute: "2-digit" });
const fmtDataHora = new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" });
const dia = (iso) => fmtDia.format(new Date(iso)).replace(".", "");
const hora = (iso) => fmtHora.format(new Date(iso));
const dataHora = (iso) => (iso ? fmtDataHora.format(new Date(iso)) : "—");
const dataLocal = (iso) => new Date(iso).toLocaleDateString("en-CA");
function duracao(inicio, fim) {
  const minutos = Math.round((new Date(fim) - new Date(inicio)) / 60000);
  const h = Math.floor(minutos / 60);
  const m = minutos % 60;
  return h ? `${h}h${m ? ` ${String(m).padStart(2, "0")}min` : ""}` : `${m}min`;
}
const normalizar = (texto) => String(texto || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
const vendasAbertas = (voo) => new Date(voo.partida) - Date.now() > 2 * 3600 * 1000;

function avisar(texto, tipo = "") {
  const aviso = document.createElement("div");
  aviso.className = `aviso ${tipo}`;
  aviso.setAttribute("role", "status");
  aviso.textContent = texto;
  $("#avisos").append(aviso);
  setTimeout(() => aviso.remove(), 5000);
}

async function ocupado(botao, tarefa) {
  if (!botao || botao.getAttribute("aria-busy") === "true") return;
  botao.setAttribute("aria-busy", "true");
  botao.disabled = true;
  try {
    await tarefa();
  } finally {
    if (botao.isConnected) {
      botao.removeAttribute("aria-busy");
      botao.disabled = false;
    }
  }
}

function mostrarErro(form, texto) {
  const caixa = $("[data-erro]", form);
  if (!caixa) return texto ? avisar(texto, "erro") : undefined;
  caixa.textContent = texto;
  caixa.hidden = !texto;
}

/* ---------- API ---------- */

class ErroApi extends Error {
  constructor(status, mensagem) {
    super(mensagem);
    this.status = status;
  }
}

const ROTULOS = {
  codigo: "Código", origem: "Origem", destino: "Destino", preco: "Preço", assentos: "Assentos",
  partida: "Partida", chegada: "Chegada", voo_id: "Voo", assento: "Assento", nome: "Nome",
  documento: "Documento", email: "E-mail", senha: "Senha", titular: "Nome no cartão",
  numero: "Número do cartão", validade: "Validade", cvv: "Código de segurança",
};

function mensagemDeErro(dados, status) {
  const detalhe = dados && dados.detail;
  if (typeof detalhe === "string") return detalhe;
  if (Array.isArray(detalhe) && detalhe.length) {
    const textos = detalhe.map((item) => {
      if (typeof item.msg === "string" && item.msg.startsWith("Value error, ")) return item.msg.slice(13);
      const campo = Array.isArray(item.loc) ? item.loc.filter((p) => typeof p === "string").pop() : "";
      return `${ROTULOS[campo] || "Campo"} inválido`;
    });
    return [...new Set(textos)].join(". ");
  }
  if (status === 0) return "Sem conexão com o servidor.";
  return status >= 500 ? "Erro no servidor. Tente novamente." : "Não foi possível concluir a operação.";
}

async function api(metodo, rota, corpo) {
  let resposta;
  try {
    resposta = await fetch(rota, {
      method: metodo,
      credentials: "same-origin",
      headers: { "X-Requested-With": "fetch", ...(corpo ? { "Content-Type": "application/json" } : {}) },
      body: corpo ? JSON.stringify(corpo) : undefined,
    });
  } catch {
    throw new ErroApi(0, mensagemDeErro(null, 0));
  }
  let dados = null;
  if (resposta.status !== 204) {
    try { dados = await resposta.json(); } catch { dados = null; }
  }
  if (!resposta.ok) {
    if (resposta.status === 401 && estado.usuario && rota !== "/auth/entrar") {
      estado.usuario = null;
      desenharTopo();
    }
    throw new ErroApi(resposta.status, mensagemDeErro(dados, resposta.status));
  }
  return dados;
}

/* ---------- Estado ---------- */

const estado = {
  usuario: null,
  notificacoes: { itens: [], nao_lidas: 0 },
  ultimaNotificacao: 0,
  voos: new Map(),
};
let limpezas = [];
const aoSair = (funcao) => limpezas.push(funcao);

async function carregarVoo(id) {
  if (!estado.voos.has(id)) estado.voos.set(id, api("GET", `/voos/${id}`).catch(() => null));
  return estado.voos.get(id);
}

/* ---------- Cabeçalho, sessão e notificações ---------- */

function desenharTopo() {
  const u = estado.usuario;
  const rota = location.hash || "#/";
  const link = (href, texto) => html`<a href="${href}" class="${rota === href ? "ativo" : ""}">${texto}</a>`;
  $("#menu").innerHTML = html`
    ${link("#/", "Voos")}
    <a href="#/" data-acao="ir-secao" data-secao="destinos">Destinos</a>
    ${u && !u.papel.includes("ADMIN") ? link("#/minhas-reservas", "Minhas reservas") : ""}
    ${u && u.papel === "ADMIN" ? link("#/admin", "Painel") : ""}
    ${link("#/politicas", "Políticas")}`.valor;

  if (!u) {
    $("#area-usuario").innerHTML = html`
      <a class="botao claro pequeno" href="#/entrar">Entrar</a>
      <a class="botao coral pequeno" href="#/cadastro">Criar conta</a>`.valor;
    return;
  }
  const n = estado.notificacoes.nao_lidas;
  const primeiroNome = u.nome.split(" ")[0];
  $("#area-usuario").innerHTML = html`
    <div class="suspenso">
      <button class="icone-botao" type="button" data-acao="alternar" data-alvo="painel-notificacoes"
        aria-label="Notificações${n ? `, ${n} não lidas` : ""}" aria-expanded="false">
        ${icone("i-sino", 20)}${n ? html`<span class="contador">${n > 9 ? "9+" : n}</span>` : ""}
      </button>
      <div class="painel-suspenso" id="painel-notificacoes" hidden>
        <header><strong>Notificações</strong>
          ${n ? html`<button class="link-botao" type="button" data-acao="ler-todas">Marcar todas como lidas</button>` : ""}
        </header>
        <div class="lista-notificacoes">${listaNotificacoes()}</div>
      </div>
    </div>
    <div class="suspenso">
      <button class="botao claro pequeno" type="button" data-acao="alternar" data-alvo="painel-conta" aria-expanded="false">
        ${icone("i-usuario")} ${primeiroNome}
      </button>
      <div class="painel-suspenso menu-conta" id="painel-conta" hidden>
        <div class="quem"><strong>${u.nome}</strong>${u.papel === "ADMIN" ? html`<span class="selo-admin">ADMIN</span>` : ""}<small>${u.email}</small></div>
        ${u.papel === "ADMIN"
          ? html`<a href="#/admin">${icone("i-painel")} Painel administrativo</a>`
          : html`<a href="#/minhas-reservas">${icone("i-bilhete")} Minhas reservas</a>`}
        <button type="button" data-acao="sair">${icone("i-sair")} Sair</button>
      </div>
    </div>`.valor;
}

function listaNotificacoes() {
  const itens = estado.notificacoes.itens;
  if (!itens.length) return html`<p class="vazio" style="border:0;padding:24px 10px">Nenhuma notificação por enquanto.</p>`;
  return itens.map((n) => html`
    <button type="button" class="notificacao ${n.lida ? "" : "nova"}" data-acao="abrir-notificacao" data-id="${n.id}" data-reserva="${n.reserva_id || ""}">
      <strong>${n.titulo}</strong>
      <p>${n.mensagem}</p>
      <time datetime="${n.criada_em}">${dataHora(n.criada_em)}</time>
    </button>`);
}

async function atualizarNotificacoes(silencioso = false) {
  if (!estado.usuario) return;
  try {
    const dados = await api("GET", "/notificacoes");
    const maisRecente = dados.itens.length ? dados.itens[0].id : 0;
    if (silencioso && maisRecente > estado.ultimaNotificacao && !dados.itens[0].lida) avisar(dados.itens[0].titulo);
    estado.ultimaNotificacao = maisRecente;
    const aberto = $$(".painel-suspenso").find((p) => !p.hidden)?.id;
    estado.notificacoes = dados;
    desenharTopo();
    if (aberto && document.getElementById(aberto)) {
      document.getElementById(aberto).hidden = false;
      $(`[data-alvo="${aberto}"]`)?.setAttribute("aria-expanded", "true");
    }
  } catch { /* falha temporária: tenta de novo no próximo ciclo */ }
}

setInterval(() => atualizarNotificacoes(true), 20000);

async function iniciarSessao() {
  try {
    estado.usuario = await api("GET", "/auth/eu");
  } catch {
    estado.usuario = null;
  }
  desenharTopo();
  await atualizarNotificacoes();
}

function exigirLogin(admin = false) {
  if (!estado.usuario) {
    location.hash = `#/entrar?volta=${encodeURIComponent(location.hash)}`;
    return false;
  }
  if (admin && estado.usuario.papel !== "ADMIN") {
    montar(html`<div class="container pagina"><div class="vazio">Esta área é restrita ao administrador.</div></div>`);
    return false;
  }
  return true;
}

/* ---------- Página inicial ---------- */

const SLIDES = [
  { img: "ceu-dourado.jpg", etiqueta: "Sua próxima decolagem", titulo: "Voe além do horizonte",
    texto: "Escolha o voo, marque seu assento no mapa da cabine e pague com segurança em poucos minutos." },
  { img: "rio-de-janeiro.jpg", etiqueta: "Destino em alta", titulo: "O Rio de Janeiro te espera",
    texto: "Pão de Açúcar, praias e pôr do sol na Baía de Guanabara. Garanta já o seu lugar." },
  { img: "natal.jpg", etiqueta: "Nordeste", titulo: "Sol, mar e tarifas que cabem na viagem",
    texto: "Natal, Fortaleza e Salvador com voos diretos e escolha de assento inclusa." },
  { img: "crepusculo.jpg", etiqueta: "Viaje tranquilo", titulo: "Cancele grátis em até 24 horas",
    texto: "Mudou de planos? Cancele em até 24 horas após a compra e receba o valor de volta." },
];

const DESTINOS = [
  { nome: "Rio de Janeiro", img: "rio-de-janeiro.jpg", texto: "Cidade Maravilhosa" },
  { nome: "Fortaleza", img: "fortaleza.jpg", texto: "Praias de águas mornas" },
  { nome: "Natal", img: "natal.jpg", texto: "Ponta Negra e dunas" },
  { nome: "Salvador", img: "salvador.jpg", texto: "Pelourinho e cultura" },
  { nome: "São Paulo", img: "sao-paulo.jpg", texto: "Avenida Paulista" },
  { nome: "Lisboa", img: "lisboa.jpg", texto: "Bondes e miradouros" },
];

async function telaInicio(params) {
  montar(html`
    <section class="carrossel" aria-roledescription="carrossel" aria-label="Destaques">
      ${SLIDES.map((s, i) => html`
        <div class="slide ${i === 0 ? "ativo" : ""}" role="group" aria-roledescription="slide" aria-label="${i + 1} de ${SLIDES.length}" ${i ? seguro('aria-hidden="true"') : ""}>
          <img src="/static/img/${s.img}" alt="" ${i ? seguro('loading="lazy"') : ""}>
          <div class="slide-texto"><div class="container">
            <span class="etiqueta">${s.etiqueta}</span>
            ${i === 0 ? html`<h1>${s.titulo}</h1>` : html`<h2>${s.titulo}</h2>`}
            <p>${s.texto}</p>
            <div class="acoes">
              <a class="botao coral" href="#/" data-acao="ir-secao" data-secao="voos">${icone("i-lupa")} Ver voos</a>
              ${estado.usuario ? "" : html`<a class="botao vazado" href="#/cadastro">Criar conta grátis</a>`}
            </div>
          </div></div>
        </div>`)}
      <div class="carrossel-controles"><div class="container" style="display:flex;justify-content:space-between;align-items:center">
        <div class="pontos" role="tablist" aria-label="Escolher destaque">
          ${SLIDES.map((s, i) => html`<button class="ponto ${i === 0 ? "ativo" : ""}" type="button" data-acao="slide" data-indice="${i}" aria-label="Destaque ${i + 1}: ${s.titulo}"></button>`)}
        </div>
        <div class="setas">
          <button class="seta" type="button" data-acao="slide-anterior" aria-label="Destaque anterior">${icone("i-anterior", 20)}</button>
          <button class="seta" type="button" data-acao="slide-proximo" aria-label="Próximo destaque">${icone("i-proximo", 20)}</button>
        </div>
      </div></div>
    </section>

    <div class="container">
      <form class="busca" data-form="busca" id="busca" role="search">
        <h2>${icone("i-lupa", 20)} Encontre sua passagem</h2>
        <div class="campos">
          <div class="campo"><label for="b-origem">Origem</label><input id="b-origem" name="origem" list="cidades" placeholder="De onde você sai?" autocomplete="off" value="${params.get("origem") || ""}"></div>
          <div class="campo"><label for="b-destino">Destino</label><input id="b-destino" name="destino" list="cidades" placeholder="Para onde vai?" autocomplete="off" value="${params.get("destino") || ""}"></div>
          <div class="campo"><label for="b-data">Data da ida</label><input id="b-data" name="data" type="date" value="${params.get("data") || ""}"></div>
          <button class="botao coral" type="submit">${icone("i-lupa")} Buscar voos</button>
        </div>
        <datalist id="cidades"></datalist>
      </form>
    </div>

    <section class="bloco" id="voos">
      <div class="container">
        <div class="titulo-secao">
          <div><span class="sobretitulo">Voos disponíveis</span><h2>Para onde vamos?</h2><p id="resumo-busca"></p></div>
          <button class="botao claro pequeno" type="button" data-acao="limpar-busca">Limpar filtros</button>
        </div>
        <div class="lista-voos" id="lista-voos"><div class="carregando">Carregando voos…</div></div>
      </div>
    </section>

    <section class="bloco" id="destinos">
      <div class="container">
        <div class="titulo-secao"><div><span class="sobretitulo">Inspiração</span><h2>Destinos em destaque</h2></div></div>
        <div class="destinos" id="grade-destinos"></div>
      </div>
    </section>

    <section class="bloco">
      <div class="container">
        <div class="titulo-secao"><div><span class="sobretitulo">Por que ELVoo</span><h2>Viaje com tranquilidade</h2></div></div>
        <div class="vantagens">
          <div class="vantagem"><div class="icone">${icone("i-escudo", 24)}</div><h3>Pagamento seguro</h3><p>Dados do cartão nunca ficam guardados: armazenamos só a bandeira e os 4 últimos dígitos.</p></div>
          <div class="vantagem"><div class="icone">${icone("i-relogio", 24)}</div><h3>Cancelamento em 24 h</h3><p>Cancele sem custo em até 24 horas após a confirmação e receba o reembolso integral.</p></div>
          <div class="vantagem"><div class="icone">${icone("i-assento", 24)}</div><h3>Escolha de assento</h3><p>Veja o mapa da cabine e escolha seu lugar no momento da compra, sem taxa extra.</p></div>
          <div class="vantagem"><div class="icone">${icone("i-sino", 24)}</div><h3>Avisos na sua conta</h3><p>Acompanhe criação, pagamento e cancelamento da reserva em tempo real.</p></div>
        </div>
      </div>
    </section>`);

  iniciarCarrossel();
  try {
    const voos = await api("GET", "/voos");
    estado.listaVoos = voos;
    voos.forEach((v) => estado.voos.set(v.id, Promise.resolve(v)));
    const cidades = [...new Set(voos.flatMap((v) => [v.origem, v.destino]))].sort();
    $("#cidades").innerHTML = cidades.map((c) => html`<option value="${c}">`.valor).join("");
    desenharVoos();
    desenharDestinos();
    if (params.get("secao")) rolarPara(params.get("secao"));
  } catch (erro) {
    $("#lista-voos").innerHTML = html`<div class="vazio">${erro.message}</div>`.valor;
  }
}

function filtrosBusca() {
  const form = $("#busca");
  return form ? Object.fromEntries(new FormData(form)) : {};
}

function desenharVoos() {
  const alvo = $("#lista-voos");
  if (!alvo) return;
  const { origem = "", destino = "", data = "" } = filtrosBusca();
  const todos = estado.listaVoos || [];
  const voos = todos.filter((v) =>
    (!origem || normalizar(v.origem).includes(normalizar(origem))) &&
    (!destino || normalizar(v.destino).includes(normalizar(destino))) &&
    (!data || dataLocal(v.partida) === data));
  $("#resumo-busca").textContent = todos.length ? `${voos.length} de ${todos.length} voos` : "";
  if (!todos.length) {
    alvo.innerHTML = html`<div class="vazio">Nenhum voo à venda no momento. Volte em breve!</div>`.valor;
    return;
  }
  if (!voos.length) {
    alvo.innerHTML = html`<div class="vazio">Nenhum voo encontrado com esses filtros. Tente outra data ou cidade.</div>`.valor;
    return;
  }
  alvo.innerHTML = voos.map(cartaoVoo).map((c) => c.valor).join("");
}

function cartaoVoo(v) {
  const semLugar = v.assentos_livres === 0;
  return html`
    <article class="voo">
      <div>
        <div class="voo-trecho">
          <div class="voo-ponto"><strong>${hora(v.partida)}</strong><span>${v.origem}</span></div>
          <div class="voo-linha"><span>${duracao(v.partida, v.chegada)} · direto</span></div>
          <div class="voo-ponto fim"><strong>${hora(v.chegada)}</strong><span>${v.destino}</span></div>
        </div>
        <div class="voo-meta"><span>${dia(v.partida)}</span><span>Voo ${v.codigo}</span><span>Bagagem de mão inclusa</span></div>
      </div>
      <div class="voo-preco">
        <div><small>por pessoa</small><strong>${moeda.format(v.preco)}</strong></div>
        <span class="livres ${semLugar ? "zero" : ""}">${semLugar ? "Esgotado" : `${v.assentos_livres} assento${v.assentos_livres === 1 ? "" : "s"} livre${v.assentos_livres === 1 ? "" : "s"}`}</span>
        ${semLugar ? html`<button class="botao pequeno" disabled>Esgotado</button>` : html`<a class="botao pequeno" href="#/voo/${v.id}">Selecionar</a>`}
      </div>
    </article>`;
}

function desenharDestinos() {
  const voos = estado.listaVoos || [];
  $("#grade-destinos").innerHTML = DESTINOS.map((d) => {
    const precos = voos.filter((v) => normalizar(v.destino).includes(normalizar(d.nome))).map((v) => v.preco);
    const chamada = precos.length ? `a partir de ${moeda.format(Math.min(...precos))}` : d.texto;
    return html`
      <button class="destino" type="button" data-acao="buscar-destino" data-destino="${d.nome}">
        <img src="/static/img/${d.img}" alt="" loading="lazy">
        <span class="destino-texto"><strong>${d.nome}</strong><span>${chamada}</span></span>
      </button>`.valor;
  }).join("");
}

function iniciarCarrossel() {
  const slides = $$(".slide");
  const pontos = $$(".ponto");
  const carrossel = $(".carrossel");
  let atual = 0;
  let pausado = false;
  const mostrar = (indice) => {
    atual = (indice + slides.length) % slides.length;
    slides.forEach((s, i) => {
      s.classList.toggle("ativo", i === atual);
      s.setAttribute("aria-hidden", String(i !== atual));
      s.inert = i !== atual;
    });
    pontos.forEach((p, i) => p.classList.toggle("ativo", i === atual));
  };
  estado.carrossel = { mostrar, atual: () => atual };
  mostrar(0);
  const reduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const relogio = reduzido ? null : setInterval(() => { if (!pausado && !document.hidden) mostrar(atual + 1); }, 6500);
  carrossel.addEventListener("mouseenter", () => { pausado = true; });
  carrossel.addEventListener("mouseleave", () => { pausado = false; });
  carrossel.addEventListener("focusin", () => { pausado = true; });
  carrossel.addEventListener("focusout", () => { pausado = false; });
  aoSair(() => { clearInterval(relogio); estado.carrossel = null; });
}

function rolarPara(id) {
  const alvo = document.getElementById(id);
  if (alvo) alvo.scrollIntoView({ behavior: "smooth", block: "start" });
}

/* ---------- Entrar e cadastrar ---------- */

function telaAcesso(modo, params) {
  if (estado.usuario) {
    location.hash = params.get("volta") || "#/";
    return;
  }
  const cadastro = modo === "cadastro";
  const volta = params.get("volta") || "";
  const sufixo = volta ? `?volta=${encodeURIComponent(volta)}` : "";
  montar(html`
    <div class="auth">
      <div class="auth-foto">
        <img src="/static/img/janela.jpg" alt="Vista da janela do avião acima das nuvens ao pôr do sol">
        <blockquote>
          <p>“A melhor vista do mundo é a da janela, a caminho de um lugar novo.”</p>
          <ul>
            <li>${icone("i-escudo")} Senha protegida com criptografia</li>
            <li>${icone("i-sino")} Avisos da sua reserva na sua conta</li>
            <li>${icone("i-relogio")} Cancelamento gratuito em até 24 horas</li>
          </ul>
        </blockquote>
      </div>
      <div class="auth-lado">
        <div class="auth-cartao">
          <span class="sobretitulo">${cadastro ? "Bem-vindo ao ELVoo" : "Que bom te ver de novo"}</span>
          <h1>${cadastro ? "Crie sua conta" : "Entre na sua conta"}</h1>
          <p class="subtitulo">${cadastro ? "Leva menos de um minuto e você acompanha todas as suas viagens." : "Acesse suas reservas, pagamentos e notificações."}</p>
          ${volta ? html`<div class="mensagem info">Entre ou crie uma conta para continuar sua compra.</div>` : ""}
          <div class="abas" role="tablist">
            <a class="aba" role="tab" href="#/entrar${sufixo}" aria-selected="${!cadastro}">Entrar</a>
            <a class="aba" role="tab" href="#/cadastro${sufixo}" aria-selected="${cadastro}">Criar conta</a>
          </div>
          ${cadastro ? formCadastro(volta) : formEntrar(volta)}
          <p class="seguro">${icone("i-cadeado", 16)} Conexão protegida. Nunca pedimos sua senha por e-mail.</p>
        </div>
      </div>
    </div>`);
  $("input", app)?.focus();
}

const campoSenha = (id, nome, rotulo, autocomplete) => html`
  <div class="campo"><label for="${id}">${rotulo}</label>
    <div class="campo-senha">
      <input id="${id}" name="${nome}" type="password" required minlength="8" maxlength="128" autocomplete="${autocomplete}">
      <button type="button" data-acao="mostrar-senha" data-alvo="${id}" aria-label="Mostrar senha">${icone("i-olho")}</button>
    </div>
  </div>`;

const formEntrar = (volta) => html`
  <form class="formulario" data-form="entrar" data-volta="${volta}" novalidate>
    <div class="mensagem erro" data-erro hidden></div>
    <div class="campo"><label for="l-email">E-mail</label><input id="l-email" name="email" type="email" required maxlength="120" autocomplete="email"></div>
    ${campoSenha("l-senha", "senha", "Senha", "current-password")}
    <button class="botao coral largo" type="submit">Entrar</button>
  </form>`;

const formCadastro = (volta) => html`
  <form class="formulario" data-form="cadastro" data-volta="${volta}" novalidate>
    <div class="mensagem erro" data-erro hidden></div>
    <div class="campo"><label for="c-nome">Nome completo</label><input id="c-nome" name="nome" required minlength="2" maxlength="120" autocomplete="name"></div>
    <div class="campo"><label for="c-email">E-mail</label><input id="c-email" name="email" type="email" required maxlength="120" autocomplete="email"></div>
    ${campoSenha("c-senha", "senha", "Senha", "new-password")}
    <div class="forca" aria-hidden="true"><span id="forca-barra"></span></div>
    <small id="forca-texto" class="campo">Use pelo menos 8 caracteres, com letras e números.</small>
    ${campoSenha("c-senha2", "senha2", "Confirme a senha", "new-password")}
    <label class="marcar"><input type="checkbox" name="aceite_termos" required>
      <span>Li e aceito os <a href="#/politicas#termos">termos de uso</a> e a <a href="#/politicas#privacidade">política de privacidade</a>.</span></label>
    <button class="botao coral largo" type="submit">Criar conta</button>
  </form>`;

function avaliarSenha(senha) {
  let pontos = 0;
  if (senha.length >= 8) pontos++;
  if (senha.length >= 12) pontos++;
  if (/[a-z]/.test(senha) && /[A-Z]/.test(senha)) pontos++;
  if (/\d/.test(senha)) pontos++;
  if (/[^A-Za-z0-9]/.test(senha)) pontos++;
  const niveis = [["Muito fraca", "#b91c1c"], ["Fraca", "#dc2626"], ["Razoável", "#d97706"], ["Boa", "#0f766e"], ["Forte", "#15803d"], ["Excelente", "#15803d"]];
  return { pontos, rotulo: niveis[pontos][0], cor: niveis[pontos][1] };
}

async function entrarComo(usuario, volta) {
  estado.usuario = usuario;
  estado.voos.clear();
  desenharTopo();
  await atualizarNotificacoes();
  location.hash = volta || (usuario.papel === "ADMIN" ? "#/admin" : "#/");
}

/* ---------- Escolha de assento ---------- */

async function telaVoo(id) {
  montar(html`<div class="container carregando">Carregando voo…</div>`);
  estado.voos.delete(id);
  const voo = await carregarVoo(id);
  if (!voo) {
    montar(html`<div class="container pagina"><div class="vazio">Voo não encontrado. <a href="#/">Ver voos disponíveis</a></div></div>`);
    return;
  }
  estado.compra = { voo, assento: null };
  const u = estado.usuario;
  montar(html`
    <div class="container pagina">
      <a href="#/" class="link-botao">← Voltar aos voos</a>
      <h1>${voo.origem} → ${voo.destino}</h1>
      <p class="subtitulo">${dia(voo.partida)} · ${hora(voo.partida)} – ${hora(voo.chegada)} · ${duracao(voo.partida, voo.chegada)} · Voo ${voo.codigo}</p>
      ${voo.vendas_abertas ? "" : html`<div class="mensagem alerta">As vendas deste voo foram encerradas.</div>`}
      <div class="grade-compra">
        <div class="painel">
          <h2 class="passo"><i>1</i> Escolha o assento</h2>
          <div class="aviao"><div class="cabine" id="cabine"></div></div>
          <div class="legenda"><span><i></i> Livre</span><span><i class="e"></i> Escolhido</span><span><i class="o"></i> Ocupado</span></div>
          <h2 class="passo" style="margin-top:28px"><i>2</i> Dados do passageiro</h2>
          ${u ? html`
            <form class="formulario" data-form="reservar" novalidate>
              <div class="mensagem erro" data-erro hidden></div>
              <div class="campo"><label for="p-nome">Nome completo (como no documento)</label><input id="p-nome" name="nome" required minlength="2" maxlength="120" value="${u.papel === "ADMIN" ? "" : u.nome}" autocomplete="name"></div>
              <div class="duas">
                <div class="campo"><label for="p-documento">CPF ou passaporte</label><input id="p-documento" name="documento" required minlength="5" maxlength="30" pattern="[A-Za-z0-9.\\-]{5,30}"><small>Letras, números, ponto e hífen</small></div>
                <div class="campo"><label for="p-email">E-mail do passageiro</label><input id="p-email" name="email" type="email" required maxlength="120" value="${u.papel === "ADMIN" ? "" : u.email}"></div>
              </div>
              <button class="botao coral" type="submit" id="continuar" disabled>${icone("i-cartao")} Continuar para o pagamento</button>
            </form>`
          : html`
            <div class="mensagem info">Para reservar, entre na sua conta ou crie uma em menos de um minuto.</div>
            <p><a class="botao coral" href="#/entrar?volta=${encodeURIComponent(location.hash)}">Entrar para continuar</a></p>`}
        </div>
        <aside class="painel resumo">
          <h2 class="passo">Resumo da compra</h2>
          <dl>
            <dt>Voo</dt><dd>${voo.codigo}</dd>
            <dt>Ida</dt><dd>${dia(voo.partida)}, ${hora(voo.partida)}</dd>
            <dt>Trecho</dt><dd>${voo.origem} → ${voo.destino}</dd>
            <dt>Assento</dt><dd id="resumo-assento">—</dd>
            <dt>Tarifa</dt><dd>${moeda.format(voo.preco)}</dd>
          </dl>
          <div class="total"><span>Total</span><strong>${moeda.format(voo.preco)}</strong></div>
          <ul class="politica-curta">
            <li>${icone("i-relogio", 16)} Pagamento em até 15 minutos para garantir o assento.</li>
            <li>${icone("i-escudo", 16)} Cancelamento gratuito em até 24 horas após a confirmação.</li>
            <li>${icone("i-bilhete", 16)} Bagagem de mão de até 10 kg inclusa.</li>
          </ul>
        </aside>
      </div>
    </div>`);
  desenharCabine();
}

function desenharCabine() {
  const { voo, assento } = estado.compra;
  const porFila = new Map();
  const letras = new Set();
  for (const a of voo.assentos) {
    const m = /^(\d+)([A-Z])$/.exec(a.numero);
    if (!m) continue;
    letras.add(m[2]);
    if (!porFila.has(+m[1])) porFila.set(+m[1], new Map());
    porFila.get(+m[1]).set(m[2], a);
  }
  const colunas = [...letras].sort();
  const corredor = Math.ceil(colunas.length / 2);
  const aberto = voo.vendas_abertas;
  $("#cabine").innerHTML = [...porFila.keys()].sort((a, b) => a - b).map((fila) => html`
    <div class="fila"><span class="n">${fila}</span>
      ${colunas.map((letra, i) => {
        const a = porFila.get(fila).get(letra);
        const espaco = i === corredor && colunas.length > 1 ? html`<span class="corredor"></span>` : "";
        if (!a) return html`${espaco}<span class="assento fantasma"></span>`;
        const livre = a.status === "LIVRE" && aberto;
        const escolhido = assento === a.numero;
        return html`${espaco}<button type="button" class="assento ${livre ? "" : "bloqueado"} ${escolhido ? "escolhido" : ""}"
          data-acao="assento" data-numero="${a.numero}" ${livre ? "" : seguro("disabled")}
          aria-pressed="${escolhido}" aria-label="Assento ${a.numero}${livre ? "" : ", indisponível"}">${letra}</button>`;
      })}
      <span class="n">${fila}</span></div>`.valor).join("");
  $("#resumo-assento").textContent = assento || "—";
  const botao = $("#continuar");
  if (botao) botao.disabled = !assento;
}

/* ---------- Pagamento ---------- */

const CARTOES_TESTE = [
  ["4242 4242 4242 4242", "aprovado"],
  ["4000 0000 0000 0002", "recusado pelo banco"],
  ["4000 0000 0000 9995", "saldo insuficiente"],
];

function bandeiraCartao(numero) {
  if (/^(4011|4312|4389|5041|5066|5067|6277|6362|6363|6504|6505|6516)/.test(numero)) return "Elo";
  if (/^3[47]/.test(numero)) return "Amex";
  if (/^4/.test(numero)) return "Visa";
  if (/^(5[1-5]|2[2-7])/.test(numero)) return "Mastercard";
  return "";
}

function formatarNumeroCartao(valor) {
  const d = valor.replace(/\D/g, "").slice(0, 19);
  if (/^3[47]/.test(d)) return [d.slice(0, 4), d.slice(4, 10), d.slice(10, 15)].filter(Boolean).join(" ");
  return d.replace(/(\d{4})(?=\d)/g, "$1 ");
}

async function telaPagamento(reservaId) {
  if (!exigirLogin()) return;
  montar(html`<div class="container carregando">Carregando pagamento…</div>`);
  let reserva;
  try {
    reserva = await api("GET", `/reservas/${reservaId}`);
  } catch (erro) {
    montar(html`<div class="container pagina"><div class="vazio">${erro.message}</div></div>`);
    return;
  }
  if (reserva.status === "CONFIRMADA") {
    location.hash = `#/bilhete/${reservaId}`;
    return;
  }
  const voo = await carregarVoo(reserva.voo_id);
  if (reserva.status === "CANCELADA") {
    montar(html`<div class="container pagina"><h1>Reserva ${reserva.localizador} cancelada</h1>
      <div class="mensagem erro">${reserva.motivo_cancelamento || "Esta reserva foi cancelada."}</div>
      <p><a class="botao" href="#/">Escolher outro voo</a></p></div>`);
    return;
  }
  montar(html`
    <div class="container pagina">
      <span class="sobretitulo">Pagamento seguro</span>
      <h1>Finalize sua compra</h1>
      <p class="subtitulo">Reserva <strong>${reserva.localizador}</strong> · assento ${reserva.assento} garantido até o fim do prazo.</p>
      <div class="grade-compra">
        <div class="painel">
          <div class="cronometro" id="cronometro">${icone("i-relogio", 20)} <span>Tempo para pagar:</span> <strong id="tempo">--:--</strong></div>
          <div class="cartao-visual" aria-hidden="true">
            <span class="marca-cartao" id="cv-bandeira"></span>
            <div class="chip"></div>
            <div class="numero" id="cv-numero">•••• •••• •••• ••••</div>
            <div class="linha"><div><small>Titular</small><span id="cv-titular">SEU NOME</span></div><div><small>Validade</small><span id="cv-validade">MM/AA</span></div></div>
          </div>
          <form class="formulario" data-form="pagar" data-reserva="${reserva.id}" novalidate autocomplete="on">
            <div class="mensagem erro" data-erro hidden></div>
            <div class="campo"><label for="k-numero">Número do cartão</label><input id="k-numero" name="numero" inputmode="numeric" autocomplete="cc-number" required placeholder="0000 0000 0000 0000" data-mascara="cartao"></div>
            <div class="campo"><label for="k-titular">Nome impresso no cartão</label><input id="k-titular" name="titular" autocomplete="cc-name" required minlength="3" maxlength="80" data-mascara="titular"></div>
            <div class="duas">
              <div class="campo"><label for="k-validade">Validade</label><input id="k-validade" name="validade" inputmode="numeric" autocomplete="cc-exp" placeholder="MM/AA" required maxlength="5" data-mascara="validade"></div>
              <div class="campo"><label for="k-cvv">CVV</label><input id="k-cvv" name="cvv" inputmode="numeric" autocomplete="cc-csc" placeholder="123" required maxlength="4" data-mascara="cvv"></div>
            </div>
            <button class="botao coral largo" type="submit">${icone("i-cadeado")} Pagar ${moeda.format(voo ? voo.preco : 0)}</button>
            <p class="seguro">${icone("i-escudo", 16)} Não armazenamos o número completo nem o CVV do seu cartão.</p>
          </form>
          <div class="teste">
            <strong>Ambiente de demonstração:</strong> nenhum valor é cobrado. Use um cartão de teste (clique para preencher), qualquer validade futura e CVV de 3 dígitos:
            <ul>${CARTOES_TESTE.map(([n, d]) => html`<li><code data-acao="usar-cartao" data-numero="${n}">${n}</code> — ${d}</li>`)}</ul>
          </div>
        </div>
        <aside class="painel resumo">
          <h2 class="passo">Sua reserva</h2>
          <dl>
            <dt>Localizador</dt><dd>${reserva.localizador}</dd>
            ${voo ? html`<dt>Trecho</dt><dd>${voo.origem} → ${voo.destino}</dd><dt>Ida</dt><dd>${dia(voo.partida)}, ${hora(voo.partida)}</dd><dt>Voo</dt><dd>${voo.codigo}</dd>` : ""}
            <dt>Assento</dt><dd>${reserva.assento}</dd>
          </dl>
          <div class="total"><span>Total</span><strong>${moeda.format(voo ? voo.preco : 0)}</strong></div>
          <ul class="politica-curta">
            <li>${icone("i-relogio", 16)} Sem pagamento no prazo, a reserva é cancelada e o assento liberado.</li>
            <li>${icone("i-escudo", 16)} Cancelamento gratuito em até 24 horas após a confirmação.</li>
          </ul>
        </aside>
      </div>
    </div>`);

  const limite = new Date(reserva.prazo_pagamento).getTime();
  const tique = () => {
    const resta = Math.max(0, limite - Date.now());
    const alvo = $("#tempo");
    if (!alvo) return;
    alvo.textContent = `${String(Math.floor(resta / 60000)).padStart(2, "0")}:${String(Math.floor(resta / 1000) % 60).padStart(2, "0")}`;
    if (resta === 0) {
      clearInterval(relogio);
      $("#cronometro").innerHTML = html`${icone("i-relogio", 20)} O prazo para pagamento terminou. A reserva será cancelada.`.valor;
      $$("[data-form=pagar] input, [data-form=pagar] button").forEach((e) => { e.disabled = true; });
    }
  };
  const relogio = setInterval(tique, 1000);
  tique();
  aoSair(() => clearInterval(relogio));
}

function atualizarCartaoVisual() {
  const numero = $("#k-numero")?.value || "";
  const digitos = numero.replace(/\D/g, "");
  $("#cv-numero").textContent = numero || "•••• •••• •••• ••••";
  $("#cv-bandeira").textContent = bandeiraCartao(digitos);
  $("#cv-titular").textContent = $("#k-titular").value || "SEU NOME";
  $("#cv-validade").textContent = $("#k-validade").value || "MM/AA";
}

/* ---------- Bilhete e reservas do cliente ---------- */

function bilhete(reserva, voo) {
  return html`
    <div class="bilhete">
      <div class="bilhete-principal">
        <div class="bilhete-topo">
          <span class="marca">${icone("i-marca", 28)} <span>EL<b>Voo</b></span></span>
          <span class="status ${reserva.status}">${reserva.status}</span>
        </div>
        ${voo ? html`
          <div class="bilhete-rota">
            <div><strong>${hora(voo.partida)}</strong><span>${voo.origem}</span></div>
            <div class="voo-linha"><span>${duracao(voo.partida, voo.chegada)}</span></div>
            <div class="voo-ponto fim"><strong>${hora(voo.chegada)}</strong><span>${voo.destino}</span></div>
          </div>` : ""}
        <div class="bilhete-dados">
          <div><span>Data</span><b>${voo ? dia(voo.partida) : "—"}</b></div>
          <div><span>Voo</span><b>${voo ? voo.codigo : `#${reserva.voo_id}`}</b></div>
          <div><span>Assento</span><b>${reserva.assento}</b></div>
          <div><span>Valor</span><b>${reserva.valor != null ? moeda.format(reserva.valor) : "—"}</b></div>
        </div>
        ${reserva.status === "CANCELADA" ? html`<p class="mensagem erro" style="margin-top:14px">${reserva.motivo_cancelamento}</p>` : ""}
      </div>
      <div class="bilhete-canhoto">
        <div><small>Localizador</small><div class="loc">${reserva.localizador}</div></div>
        <div class="barras" aria-hidden="true"></div>
        <small>Apresente um documento com foto no embarque.</small>
      </div>
    </div>`;
}

async function telaBilhete(reservaId) {
  if (!exigirLogin()) return;
  let reserva;
  try {
    reserva = await api("GET", `/reservas/${reservaId}`);
  } catch (erro) {
    montar(html`<div class="container pagina"><div class="vazio">${erro.message}</div></div>`);
    return;
  }
  const voo = await carregarVoo(reserva.voo_id);
  montar(html`
    <div class="container pagina">
      <span class="sobretitulo">${reserva.status === "CONFIRMADA" ? "Bilhete emitido" : "Sua reserva"}</span>
      <h1>${reserva.status === "CONFIRMADA" ? "Tudo certo, boa viagem!" : `Reserva ${reserva.localizador}`}</h1>
      <p class="subtitulo">${reserva.status === "CONFIRMADA" ? "Enviamos a confirmação para as notificações da sua conta." : ""}</p>
      ${bilhete(reserva, voo)}
      <div class="bilhete-acoes">
        <a class="botao" href="#/minhas-reservas">${icone("i-bilhete")} Minhas reservas</a>
        ${reserva.status === "PENDENTE" ? html`<a class="botao coral" href="#/pagamento/${reserva.id}">Pagar agora</a>` : ""}
        <a class="botao claro" href="#/">Buscar outro voo</a>
      </div>
    </div>`);
}

async function telaMinhasReservas() {
  if (!exigirLogin()) return;
  if (estado.usuario.papel === "ADMIN") {
    location.hash = "#/admin/reservas";
    return;
  }
  montar(html`<div class="container carregando">Carregando suas reservas…</div>`);
  let reservas;
  try {
    reservas = await api("GET", "/reservas");
  } catch (erro) {
    montar(html`<div class="container pagina"><div class="vazio">${erro.message}</div></div>`);
    return;
  }
  const voos = new Map(await Promise.all([...new Set(reservas.map((r) => r.voo_id))].map(async (id) => [id, await carregarVoo(id)])));
  montar(html`
    <div class="container pagina">
      <span class="sobretitulo">Área do cliente</span>
      <h1>Minhas reservas</h1>
      <p class="subtitulo">Acompanhe pagamentos, emita bilhetes e cancele dentro do prazo.</p>
      <div class="reservas">
        ${reservas.length ? reservas.map((r) => itemReserva(r, voos.get(r.voo_id)))
          : html`<div class="vazio">Você ainda não tem reservas. <a href="#/">Encontre um voo</a></div>`}
      </div>
    </div>`);
}

function itemReserva(r, voo) {
  return html`
    <article class="reserva-item" id="reserva-${r.id}">
      <div>
        <span class="status ${r.status}">${r.status === "PENDENTE" ? "AGUARDANDO PAGAMENTO" : r.status}</span>
        <h3>${voo ? `${voo.origem} → ${voo.destino}` : `Voo #${r.voo_id}`}</h3>
        <div class="detalhes">
          <span>Localizador <strong>${r.localizador}</strong></span>
          ${voo ? html`<span>${dia(voo.partida)}, ${hora(voo.partida)}</span><span>Voo ${voo.codigo}</span>` : ""}
          <span>Assento ${r.assento}</span>
          ${r.valor != null ? html`<span>${moeda.format(r.valor)}</span>` : ""}
          ${r.status === "PENDENTE" && r.prazo_pagamento ? html`<span>Pagar até ${hora(r.prazo_pagamento)}</span>` : ""}
          ${r.status === "CANCELADA" ? html`<span>${r.motivo_cancelamento}</span>` : ""}
        </div>
      </div>
      <div class="acoes">
        ${r.status === "PENDENTE" ? html`<a class="botao coral pequeno" href="#/pagamento/${r.id}">Pagar agora</a>` : ""}
        ${r.status === "CONFIRMADA" ? html`<a class="botao pequeno" href="#/bilhete/${r.id}">Ver bilhete</a>` : ""}
        ${r.cancelavel ? html`<button class="botao perigo pequeno" type="button" data-acao="pedir-cancelamento" data-id="${r.id}">Cancelar</button>` : ""}
      </div>
      <div class="confirmar-cancelamento" id="confirmar-${r.id}" hidden>
        <div class="mensagem alerta">
          ${r.status === "CONFIRMADA" ? "O valor pago será estornado em até 7 dias úteis. " : ""}Ao cancelar, o assento ${r.assento} é liberado e não poderá ser recuperado.
          <div class="bilhete-acoes">
            <button class="botao perigo pequeno" type="button" data-acao="confirmar-cancelamento" data-id="${r.id}">Confirmar cancelamento</button>
            <button class="botao claro pequeno" type="button" data-acao="desistir-cancelamento" data-id="${r.id}">Manter reserva</button>
          </div>
        </div>
      </div>
    </article>`;
}

/* ---------- Painel administrativo ---------- */

const ABAS_ADMIN = [["visao", "Visão geral"], ["voos", "Voos e preços"], ["reservas", "Reservas"], ["pagamentos", "Pagamentos"]];

async function telaAdmin(aba = "visao") {
  if (!exigirLogin(true)) return;
  montar(html`
    <div class="container pagina">
      <span class="sobretitulo">Administração</span>
      <h1>Painel ELVoo</h1>
      <nav class="abas-admin">${ABAS_ADMIN.map(([id, nome]) => html`<a href="#/admin/${id}" class="${aba === id ? "ativo" : ""}">${nome}</a>`)}</nav>
      <div id="conteudo-admin" class="carregando">Carregando…</div>
    </div>`);
  try {
    const telas = { visao: adminVisao, voos: adminVoos, reservas: adminReservas, pagamentos: adminPagamentos };
    $("#conteudo-admin").innerHTML = (await (telas[aba] || adminVisao)()).valor;
    $("#conteudo-admin").classList.remove("carregando");
  } catch (erro) {
    $("#conteudo-admin").innerHTML = html`<div class="vazio">${erro.message}</div>`.valor;
  }
}

async function dadosAdmin() {
  const [voos, reservas, pagamentos] = await Promise.all([
    api("GET", "/voos?incluir_encerrados=true"), api("GET", "/reservas"), api("GET", "/pagamentos"),
  ]);
  voos.forEach((v) => estado.voos.set(v.id, Promise.resolve(v)));
  return { voos, reservas, pagamentos, porId: new Map(voos.map((v) => [v.id, v])) };
}

async function adminVisao() {
  const { voos, reservas, pagamentos, porId } = await dadosAdmin();
  const receita = pagamentos.filter((p) => p.status === "PAGO").reduce((t, p) => t + p.valor, 0);
  const recusas = pagamentos.flatMap((p) => p.tentativas).filter((t) => !t.aprovada).length;
  const notificacoes = estado.notificacoes.itens.slice(0, 6);
  return html`
    <div class="metricas">
      <div class="metrica"><span>Voos à venda</span><strong>${voos.filter(vendasAbertas).length}</strong></div>
      <div class="metrica"><span>Reservas confirmadas</span><strong>${reservas.filter((r) => r.status === "CONFIRMADA").length}</strong></div>
      <div class="metrica"><span>Receita confirmada</span><strong>${moeda.format(receita)}</strong></div>
      <div class="metrica"><span>Pagamentos recusados</span><strong>${recusas}</strong></div>
    </div>
    <div class="grade-admin">
      <div class="painel"><h2 class="passo">Últimas notificações</h2>
        <div class="lista-notificacoes">${notificacoes.length
          ? notificacoes.map((n) => html`<div class="notificacao ${n.lida ? "" : "nova"}"><strong>${n.titulo}</strong><p>${n.mensagem}</p><time>${dataHora(n.criada_em)}</time></div>`)
          : html`<p class="vazio">Sem notificações.</p>`}</div>
      </div>
      <div class="painel"><h2 class="passo">Reservas recentes</h2>${tabelaReservas(reservas.slice(0, 6), porId, false)}</div>
    </div>`;
}

async function adminVoos() {
  const { voos } = await dadosAdmin();
  return html`
    <div class="grade-admin">
      <div class="painel">
        <h2 class="passo">Cadastrar voo</h2>
        <form class="formulario" data-form="novo-voo" novalidate>
          <div class="mensagem erro" data-erro hidden></div>
          <div class="tres">
            <div class="campo"><label for="v-codigo">Código</label><input id="v-codigo" name="codigo" required minlength="3" maxlength="20" pattern="[A-Za-z0-9]{3,20}" placeholder="EL1020"></div>
            <div class="campo"><label for="v-origem">Origem</label><input id="v-origem" name="origem" required minlength="3" maxlength="50" placeholder="Fortaleza"></div>
            <div class="campo"><label for="v-destino">Destino</label><input id="v-destino" name="destino" required minlength="3" maxlength="50" placeholder="Recife"></div>
          </div>
          <div class="duas">
            <div class="campo"><label for="v-partida">Partida</label><input id="v-partida" name="partida" type="datetime-local" required></div>
            <div class="campo"><label for="v-chegada">Chegada</label><input id="v-chegada" name="chegada" type="datetime-local" required></div>
          </div>
          <div class="tres">
            <div class="campo"><label for="v-preco">Preço (R$)</label><input id="v-preco" name="preco" type="number" min="0.01" max="100000" step="0.01" required placeholder="799.90"></div>
            <div class="campo"><label for="v-filas">Fileiras</label><input id="v-filas" name="filas" type="number" min="1" max="75" value="10" required></div>
            <div class="campo"><label for="v-letras">Letras</label><input id="v-letras" name="letras" required pattern="[A-Za-z]{1,10}" value="ABCDEF"></div>
          </div>
          <button class="botao coral" type="submit">Cadastrar voo</button>
        </form>
      </div>
      <div class="painel">
        <h2 class="passo">Regras de venda</h2>
        <ul class="politica-curta">
          <li>${icone("i-relogio", 16)} Vendas encerram 2 horas antes da partida.</li>
          <li>${icone("i-cartao", 16)} Alterar o preço vale para novas reservas; reservas já criadas mantêm o valor bloqueado.</li>
          <li>${icone("i-assento", 16)} Assentos no formato fileira + letra (ex.: 12A), até 300 por voo.</li>
          <li>${icone("i-escudo", 16)} Cancelamentos feitos pela companhia são estornados integralmente.</li>
        </ul>
      </div>
    </div>
    <h2 class="passo" style="margin-top:28px">Voos cadastrados</h2>
    <div class="tabela-envolta"><table>
      <thead><tr><th>Voo</th><th>Trecho</th><th>Partida</th><th>Ocupação</th><th>Situação</th><th>Preço</th></tr></thead>
      <tbody>${voos.length ? voos.map((v) => html`<tr>
        <td><strong>${v.codigo}</strong></td><td>${v.origem} → ${v.destino}</td><td>${dataHora(v.partida)}</td>
        <td>${v.assentos_total - v.assentos_livres}/${v.assentos_total}</td>
        <td>${vendasAbertas(v) ? html`<span class="status CONFIRMADA">À VENDA</span>` : html`<span class="status CANCELADA">ENCERRADO</span>`}</td>
        <td><form class="campo-preco" data-form="preco" data-voo="${v.id}"><input name="preco" type="number" min="0.01" max="100000" step="0.01" value="${v.preco}" aria-label="Preço do voo ${v.codigo}"><button class="botao claro pequeno" type="submit">Salvar</button></form></td>
      </tr>`) : html`<tr><td colspan="6">Nenhum voo cadastrado.</td></tr>`}</tbody>
    </table></div>`;
}

function tabelaReservas(reservas, porId, comAcoes = true) {
  return html`<div class="tabela-envolta"><table>
    <thead><tr><th>Localizador</th><th>Voo</th><th>Assento</th><th>Status</th><th>Valor</th><th>Criada</th>${comAcoes ? html`<th></th>` : ""}</tr></thead>
    <tbody>${reservas.length ? reservas.map((r) => {
      const v = porId.get(r.voo_id);
      return html`<tr>
        <td><strong>${r.localizador}</strong></td><td>${v ? `${v.codigo} · ${v.origem} → ${v.destino}` : `#${r.voo_id}`}</td>
        <td>${r.assento}</td><td><span class="status ${r.status}">${r.status}</span></td>
        <td>${r.valor != null ? moeda.format(r.valor) : "—"}</td><td>${dataHora(r.criada_em)}</td>
        ${comAcoes ? html`<td>${r.status !== "CANCELADA" ? html`<button class="botao perigo pequeno" type="button" data-acao="admin-cancelar" data-id="${r.id}">Cancelar</button>` : ""}</td>` : ""}
      </tr>`;
    }) : html`<tr><td colspan="7">Nenhuma reserva.</td></tr>`}</tbody>
  </table></div>`;
}

async function adminReservas() {
  const { reservas, porId } = await dadosAdmin();
  return html`<p class="subtitulo">Cancelamentos feitos aqui liberam o assento e geram estorno integral quando a reserva já foi paga.</p>${tabelaReservas(reservas, porId)}`;
}

async function adminPagamentos() {
  const { pagamentos } = await dadosAdmin();
  return html`<div class="tabela-envolta"><table>
    <thead><tr><th>Reserva</th><th>Valor</th><th>Status</th><th>Cartão</th><th>Tentativas</th><th>Prazo</th><th>Pago em</th></tr></thead>
    <tbody>${pagamentos.length ? pagamentos.map((p) => {
      const recusadas = p.tentativas.filter((t) => !t.aprovada);
      return html`<tr>
        <td>#${p.reserva_id}</td><td>${p.valor != null ? moeda.format(p.valor) : "—"}</td>
        <td><span class="status ${p.status}">${p.status.replace("_", " ")}</span></td>
        <td>${p.final_cartao ? `${p.bandeira} •••• ${p.final_cartao}` : "—"}</td>
        <td title="${recusadas.map((t) => t.motivo).join("; ")}">${p.tentativas.length}${recusadas.length ? ` (${recusadas.length} recusada${recusadas.length > 1 ? "s" : ""})` : ""}</td>
        <td>${dataHora(p.prazo)}</td><td>${dataHora(p.pago_em)}</td>
      </tr>`;
    }) : html`<tr><td colspan="7">Nenhum pagamento.</td></tr>`}</tbody>
  </table></div>`;
}

/* ---------- Políticas ---------- */

function telaPoliticas(ancora) {
  montar(html`
    <div class="container pagina">
      <span class="sobretitulo">Transparência</span>
      <h1>Políticas e termos</h1>
      <p class="subtitulo">Regras de compra, cancelamento e privacidade do ELVoo.</p>
      <div class="politicas">
        <nav aria-label="Seções">
          <a href="#/politicas#tarifas">Tarifas e pagamento</a>
          <a href="#/politicas#cancelamento">Cancelamento e reembolso</a>
          <a href="#/politicas#bagagem">Bagagem</a>
          <a href="#/politicas#embarque">Embarque</a>
          <a href="#/politicas#privacidade">Privacidade (LGPD)</a>
          <a href="#/politicas#termos">Termos de uso</a>
        </nav>
        <article>
          <section id="tarifas"><h2>Tarifas e pagamento</h2><ul>
            <li>O preço exibido é por passageiro e já inclui a escolha de assento.</li>
            <li>Depois de reservar, você tem <strong>15 minutos</strong> para concluir o pagamento. Sem pagamento no prazo, a reserva é cancelada e o assento liberado.</li>
            <li>Aceitamos cartões Visa, Mastercard, Elo e American Express. O bilhete é emitido assim que o pagamento é aprovado.</li>
            <li>As vendas de cada voo encerram 2 horas antes da partida.</li>
          </ul></section>
          <section id="cancelamento"><h2>Cancelamento e reembolso</h2><ul>
            <li>Reservas aguardando pagamento podem ser canceladas a qualquer momento, sem custo.</li>
            <li>Reservas pagas podem ser canceladas gratuitamente em até <strong>24 horas</strong> após a confirmação, com reembolso integral.</li>
            <li>O estorno é solicitado na hora e aparece na fatura em até <strong>7 dias úteis</strong>, conforme o emissor do cartão.</li>
            <li>Cancelamentos feitos pela companhia são sempre reembolsados integralmente.</li>
          </ul></section>
          <section id="bagagem"><h2>Bagagem</h2><ul>
            <li>Inclusa: 1 item pessoal (bolsa ou mochila) e 1 bagagem de mão de até 10 kg.</li>
            <li>Itens proibidos seguem as regras da autoridade de aviação civil.</li>
          </ul></section>
          <section id="embarque"><h2>Embarque</h2><ul>
            <li>Apresente documento oficial com foto. O nome deve ser igual ao da reserva.</li>
            <li>Chegue ao portão com pelo menos 40 minutos de antecedência em voos nacionais.</li>
          </ul></section>
          <section id="privacidade"><h2>Privacidade (LGPD)</h2><ul>
            <li>Coletamos apenas os dados necessários para emitir o bilhete: nome, documento e e-mail do passageiro e os dados da sua conta.</li>
            <li>Sua senha é guardada com hash criptográfico (scrypt) e nunca é exibida a ninguém, nem à equipe.</li>
            <li>Do cartão, guardamos somente a bandeira e os 4 últimos dígitos; número completo e CVV não são armazenados.</li>
            <li>Você pode solicitar acesso, correção ou exclusão dos seus dados pelos canais de atendimento.</li>
          </ul></section>
          <section id="termos"><h2>Termos de uso</h2><ul>
            <li>A conta é pessoal; mantenha sua senha em segredo. Após 5 tentativas erradas, o acesso é bloqueado por 15 minutos.</li>
            <li>Ao comprar, você declara que os dados dos passageiros são verdadeiros.</li>
            <li>Este é um projeto acadêmico: nenhum pagamento real é processado.</li>
          </ul></section>
        </article>
      </div>
    </div>`);
  if (ancora) requestAnimationFrame(() => rolarPara(ancora));
}

/* ---------- Roteador ---------- */

const ROTAS = [
  [/^\/?$/, (p) => telaInicio(p)],
  [/^\/entrar$/, (p) => telaAcesso("entrar", p)],
  [/^\/cadastro$/, (p) => telaAcesso("cadastro", p)],
  [/^\/voo\/(\d+)$/, (p, id) => telaVoo(+id)],
  [/^\/pagamento\/(\d+)$/, (p, id) => telaPagamento(+id)],
  [/^\/bilhete\/(\d+)$/, (p, id) => telaBilhete(+id)],
  [/^\/minhas-reservas$/, () => telaMinhasReservas()],
  [/^\/admin(?:\/(\w+))?$/, (p, aba) => telaAdmin(aba)],
  [/^\/politicas$/, (p, _, ancora) => telaPoliticas(ancora)],
];

async function rotear() {
  limpezas.forEach((f) => f());
  limpezas = [];
  const bruto = location.hash.replace(/^#/, "") || "/";
  const [caminhoComBusca, ancora] = bruto.split("#");
  const [caminho, busca = ""] = caminhoComBusca.split("?");
  const params = new URLSearchParams(busca);
  desenharTopo();
  for (const [padrao, tela] of ROTAS) {
    const m = padrao.exec(caminho);
    if (m) {
      window.scrollTo(0, 0);
      await tela(params, m[1], ancora);
      return;
    }
  }
  montar(html`<div class="container pagina"><h1>Página não encontrada</h1><p><a class="botao" href="#/">Voltar ao início</a></p></div>`);
}

/* ---------- Ações (cliques) ---------- */

function fecharSuspensos(exceto) {
  $$(".painel-suspenso").forEach((p) => {
    if (p.id !== exceto) {
      p.hidden = true;
      $(`[data-alvo="${p.id}"]`)?.setAttribute("aria-expanded", "false");
    }
  });
}

const ACOES = {
  alternar(botao) {
    const painel = document.getElementById(botao.dataset.alvo);
    fecharSuspensos(painel.id);
    painel.hidden = !painel.hidden;
    botao.setAttribute("aria-expanded", String(!painel.hidden));
  },
  async sair() {
    try { await api("POST", "/auth/sair"); } catch { /* sessão já encerrada */ }
    estado.usuario = null;
    estado.notificacoes = { itens: [], nao_lidas: 0 };
    estado.voos.clear();
    avisar("Você saiu da sua conta.");
    location.hash = "#/";
    rotear();
  },
  async "ler-todas"() {
    await api("POST", "/notificacoes/lidas").catch(() => null);
    await atualizarNotificacoes();
    $("#painel-notificacoes").hidden = false;
  },
  async "abrir-notificacao"(botao) {
    await api("POST", `/notificacoes/${botao.dataset.id}/lida`).catch(() => null);
    fecharSuspensos();
    await atualizarNotificacoes();
    const admin = estado.usuario?.papel === "ADMIN";
    location.hash = admin ? "#/admin/reservas" : "#/minhas-reservas";
  },
  "ir-secao"(link, evento) {
    evento.preventDefault();
    const secao = link.dataset.secao;
    if ($("#" + secao)) rolarPara(secao);
    else location.hash = `#/?secao=${secao}`;
  },
  slide(botao) { estado.carrossel?.mostrar(+botao.dataset.indice); },
  "slide-anterior"() { estado.carrossel?.mostrar(estado.carrossel.atual() - 1); },
  "slide-proximo"() { estado.carrossel?.mostrar(estado.carrossel.atual() + 1); },
  "limpar-busca"() {
    $("#busca").reset();
    $$("#busca input").forEach((i) => { i.value = ""; });
    desenharVoos();
  },
  "buscar-destino"(botao) {
    $("#b-destino").value = botao.dataset.destino;
    desenharVoos();
    rolarPara("voos");
  },
  "mostrar-senha"(botao) {
    const campo = document.getElementById(botao.dataset.alvo);
    const mostrar = campo.type === "password";
    campo.type = mostrar ? "text" : "password";
    botao.setAttribute("aria-label", mostrar ? "Ocultar senha" : "Mostrar senha");
  },
  assento(botao) {
    const numero = botao.dataset.numero;
    estado.compra.assento = estado.compra.assento === numero ? null : numero;
    desenharCabine();
  },
  "usar-cartao"(codigo) {
    $("#k-numero").value = codigo.dataset.numero;
    if (!$("#k-titular").value) $("#k-titular").value = (estado.usuario?.nome || "").toUpperCase();
    if (!$("#k-validade").value) $("#k-validade").value = "12/30";
    if (!$("#k-cvv").value) $("#k-cvv").value = "123";
    atualizarCartaoVisual();
  },
  "pedir-cancelamento"(botao) { $(`#confirmar-${botao.dataset.id}`).hidden = false; },
  "desistir-cancelamento"(botao) { $(`#confirmar-${botao.dataset.id}`).hidden = true; },
  async "confirmar-cancelamento"(botao) {
    await ocupado(botao, async () => {
      try {
        const r = await api("POST", `/reservas/${botao.dataset.id}/cancelar`);
        avisar(`Reserva ${r.localizador} cancelada.`, "ok");
        estado.voos.clear();
        await atualizarNotificacoes();
        telaMinhasReservas();
      } catch (erro) {
        avisar(erro.message, "erro");
      }
    });
  },
  async "admin-cancelar"(botao) {
    if (botao.dataset.confirmar !== "1") {
      botao.dataset.confirmar = "1";
      botao.textContent = "Confirmar?";
      setTimeout(() => { if (botao.isConnected) { botao.dataset.confirmar = ""; botao.textContent = "Cancelar"; } }, 4000);
      return;
    }
    await ocupado(botao, async () => {
      try {
        const r = await api("POST", `/reservas/${botao.dataset.id}/cancelar`);
        avisar(`Reserva ${r.localizador} cancelada.`, "ok");
        await atualizarNotificacoes();
        telaAdmin("reservas");
      } catch (erro) {
        avisar(erro.message, "erro");
      }
    });
  },
};

document.addEventListener("click", (evento) => {
  const alvo = evento.target.closest("[data-acao]");
  if (!evento.target.closest(".suspenso")) fecharSuspensos();
  if (alvo && ACOES[alvo.dataset.acao]) ACOES[alvo.dataset.acao](alvo, evento);
});

document.addEventListener("keydown", (evento) => {
  if (evento.key === "Escape") fecharSuspensos();
  if (estado.carrossel && document.activeElement?.closest(".carrossel")) {
    if (evento.key === "ArrowRight") ACOES["slide-proximo"]();
    if (evento.key === "ArrowLeft") ACOES["slide-anterior"]();
  }
});

/* ---------- Digitação (máscaras e indicadores) ---------- */

document.addEventListener("input", (evento) => {
  const campo = evento.target;
  if (campo.closest("#busca")) desenharVoos();
  const mascara = campo.dataset.mascara;
  if (mascara === "cartao") campo.value = formatarNumeroCartao(campo.value);
  if (mascara === "titular") campo.value = campo.value.toUpperCase().replace(/[^A-ZÀ-Ý' ]/g, "");
  if (mascara === "validade") {
    const d = campo.value.replace(/\D/g, "").slice(0, 4);
    campo.value = d.length > 2 ? `${d.slice(0, 2)}/${d.slice(2)}` : d;
  }
  if (mascara === "cvv") campo.value = campo.value.replace(/\D/g, "").slice(0, 4);
  if (mascara) atualizarCartaoVisual();
  if (campo.id === "c-senha") {
    const { pontos, rotulo, cor } = avaliarSenha(campo.value);
    $("#forca-barra").style.width = `${(pontos / 5) * 100}%`;
    $("#forca-barra").style.background = cor;
    $("#forca-texto").textContent = campo.value ? `Força da senha: ${rotulo}` : "Use pelo menos 8 caracteres, com letras e números.";
  }
});

/* ---------- Formulários ---------- */

const FORMULARIOS = {
  busca() {
    desenharVoos();
    rolarPara("voos");
  },
  async entrar(form) {
    if (!form.reportValidity()) return;
    const dados = Object.fromEntries(new FormData(form));
    await ocupado($("button[type=submit]", form), async () => {
      try {
        const usuario = await api("POST", "/auth/entrar", { email: dados.email.trim(), senha: dados.senha });
        avisar(`Olá, ${usuario.nome.split(" ")[0]}!`, "ok");
        await entrarComo(usuario, form.dataset.volta);
      } catch (erro) {
        mostrarErro(form, erro.message);
        $("#l-senha").value = "";
      }
    });
  },
  async cadastro(form) {
    if (!form.reportValidity()) return;
    const dados = Object.fromEntries(new FormData(form));
    if (!/[A-Za-z]/.test(dados.senha) || !/\d/.test(dados.senha)) return mostrarErro(form, "A senha precisa ter letras e números.");
    if (dados.senha !== dados.senha2) return mostrarErro(form, "As senhas não conferem.");
    await ocupado($("button[type=submit]", form), async () => {
      try {
        const usuario = await api("POST", "/auth/cadastro", {
          nome: dados.nome.trim(), email: dados.email.trim(), senha: dados.senha, aceite_termos: Boolean(dados.aceite_termos),
        });
        avisar("Conta criada com sucesso. Boas-vindas ao ELVoo!", "ok");
        await entrarComo(usuario, form.dataset.volta);
      } catch (erro) {
        mostrarErro(form, erro.message);
      }
    });
  },
  async reservar(form) {
    if (!estado.compra?.assento) return mostrarErro(form, "Escolha um assento no mapa.");
    if (!form.reportValidity()) return;
    const dados = Object.fromEntries(new FormData(form));
    await ocupado($("#continuar"), async () => {
      try {
        const reserva = await api("POST", "/reservas", {
          voo_id: estado.compra.voo.id,
          assento: estado.compra.assento,
          passageiro: { nome: dados.nome.trim(), documento: dados.documento.trim(), email: dados.email.trim() },
        });
        estado.voos.clear();
        await atualizarNotificacoes();
        if (reserva.status === "CANCELADA") {
          avisar(`${reserva.motivo_cancelamento}. Escolha outro assento.`, "erro");
          telaVoo(estado.compra.voo.id);
          return;
        }
        location.hash = `#/pagamento/${reserva.id}`;
      } catch (erro) {
        mostrarErro(form, erro.message);
      }
    });
  },
  async pagar(form) {
    if (!form.reportValidity()) return;
    const dados = Object.fromEntries(new FormData(form));
    await ocupado($("button[type=submit]", form), async () => {
      try {
        await api("POST", `/pagamentos/${form.dataset.reserva}`, {
          titular: dados.titular.trim(), numero: dados.numero, validade: dados.validade, cvv: dados.cvv,
        });
        avisar("Pagamento aprovado! Bilhete emitido.", "ok");
        await atualizarNotificacoes();
        location.hash = `#/bilhete/${form.dataset.reserva}`;
      } catch (erro) {
        $("#k-cvv").value = "";
        mostrarErro(form, erro.message);
        if (erro.status === 409) setTimeout(() => telaPagamento(+form.dataset.reserva), 2500);
      }
    });
  },
  async "novo-voo"(form) {
    if (!form.reportValidity()) return;
    const d = Object.fromEntries(new FormData(form));
    const letras = [...new Set(d.letras.toUpperCase())];
    const filas = Number(d.filas);
    if (filas * letras.length > 300) return mostrarErro(form, `São ${filas * letras.length} assentos; o limite é 300.`);
    const assentos = [];
    for (let f = 1; f <= filas; f++) letras.forEach((l) => assentos.push(`${f}${l}`));
    await ocupado($("button[type=submit]", form), async () => {
      try {
        const voo = await api("POST", "/voos", {
          codigo: d.codigo.trim(), origem: d.origem.trim(), destino: d.destino.trim(), preco: Number(d.preco),
          partida: new Date(d.partida).toISOString(), chegada: new Date(d.chegada).toISOString(), assentos,
        });
        avisar(`Voo ${voo.codigo} cadastrado com ${assentos.length} assentos.`, "ok");
        telaAdmin("voos");
      } catch (erro) {
        mostrarErro(form, erro.message);
      }
    });
  },
  async preco(form) {
    if (!form.reportValidity()) return;
    await ocupado($("button", form), async () => {
      try {
        const voo = await api("PATCH", `/voos/${form.dataset.voo}`, { preco: Number(form.preco.value) });
        estado.voos.delete(voo.id);
        avisar(`Preço do voo ${voo.codigo} atualizado para ${moeda.format(voo.preco)}.`, "ok");
      } catch (erro) {
        avisar(erro.message, "erro");
      }
    });
  },
};

document.addEventListener("submit", (evento) => {
  const form = evento.target;
  const tratar = FORMULARIOS[form.dataset.form];
  if (!tratar) return;
  evento.preventDefault();
  mostrarErro(form, "");
  tratar(form);
});

/* ---------- Início ---------- */

window.addEventListener("hashchange", rotear);
iniciarSessao().then(rotear);
