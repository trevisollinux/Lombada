"""Regressão da integração com o Programa de Associados da Amazon.

O link é gerado no frontend a partir da tag pública (/api/config → amazon_tag,
env AMAZON_ASSOC_TAG). Aqui garantimos que: o link usa ISBN com fallback pra
título+autor, o aviso de link de associado existe nos três idiomas e a
declaração exigida pelo programa aparece nas páginas institucionais.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]

DECLARACAO = (
    "Como participante do Programa de Associados da Amazon, o Lombada é "
    "remunerado pelas compras qualificadas efetuadas."
)


class AmazonAffiliateTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = (ROOT / "static" / "app.js").read_text(encoding="utf-8")
        cls.i18n = (ROOT / "static" / "i18n.js").read_text(encoding="utf-8")

    def test_link_usa_busca_amazon_br_com_tag(self):
        self.assertIn("https://www.amazon.com.br/s?k=", self.js)
        self.assertIn("appConfig.amazon_tag", self.js)

    def test_link_cai_para_titulo_e_autor_sem_isbn(self):
        self.assertIn("function linkAmazon(isbn,termoFallback)", self.js)
        self.assertIn("const termo=cod||(termoFallback||'').toString().trim();", self.js)

    def test_cards_de_edicao_passam_fallback_da_obra(self):
        self.assertIn(
            "const termoAmazonObra=[escolha?.titulo,escolha?.autor].filter(Boolean).join(' ');",
            self.js,
        )
        self.assertIn("botaoAmazon(e.isbn,'',termoAmazonObra)", self.js)

    def test_botao_no_detalhe_do_livro_da_estante(self):
        # modal "detalhe do livro" (estante): botão + aviso na seção Edição,
        # com fallback título+autor pra leitura registrada sem ISBN
        self.assertIn(
            "blocoAmazon(l.isbn,[l.titulo,l.autor].filter(Boolean).join(' '))",
            self.js,
        )

    def test_aviso_de_associado_perto_do_botao(self):
        self.assertIn("function blocoAmazon(isbn,termoFallback,cls)", self.js)
        self.assertIn("affiliate-note", self.js)

    def test_aviso_traduzido_nos_tres_idiomas(self):
        # pt usa chave sem aspas; en/es usam com aspas
        self.assertIn("affiliate_note: 'Link de associado", self.i18n)
        self.assertIn('"affiliate_note": "Affiliate link', self.i18n)
        self.assertIn('"affiliate_note": "Enlace de afiliado', self.i18n)

    def test_declaracao_no_rodape_institucional(self):
        from landing import _footer
        self.assertIn(DECLARACAO, _footer("/"))

    def test_declaracao_na_politica_de_privacidade(self):
        from landing import render_privacidade
        self.assertIn("Programa de Associados da Amazon", render_privacidade())


if __name__ == "__main__":
    unittest.main()
