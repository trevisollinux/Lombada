# Checklist de smoke do Lombada

Use este checklist antes e depois de mudanças de produto, banco, autenticação ou deploy.

## 1. Suíte automatizada

No ambiente compatível com o projeto:

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

A suíte existente cobre import/boot, busca e filtros, páginas públicas, PWA/manifesto, segurança de perfil, API pública, diário/capítulos e regressões já identificadas.

Falha automatizada bloqueia merge. Quando a falha depender de rede externa, o teste deve ser isolado/mocado — não simplesmente ignorado.

## 2. Saúde do deploy

```bash
curl -fsS https://SEU-DOMINIO/healthz
curl -fsS https://SEU-DOMINIO/readyz
curl -fsS https://SEU-DOMINIO/api/version
```

Esperado:

- `/healthz`: HTTP 200 e `ok: true`;
- `/readyz`: HTTP 200 e banco `ok`;
- `/api/version`: HTTP 200 e versão correspondente ao deploy.

## 3. Aplicativo e navegação

- [ ] Abrir o aplicativo em janela anônima.
- [ ] Confirmar criação automática de usuário anônimo.
- [ ] Navegar entre Estante, Buscar, Explorar e Perfil.
- [ ] Usar voltar/avançar do navegador sem tela em branco.
- [ ] Alternar tema claro/escuro.
- [ ] Alternar PT/EN/ES e verificar que a navegação continua funcional.
- [ ] Testar viewport móvel de aproximadamente 360 × 800.
- [ ] Confirmar ausência de overflow horizontal.

## 4. Busca e catálogo

- [ ] Buscar por título conhecido.
- [ ] Buscar por autor.
- [ ] Buscar por ISBN.
- [ ] Aplicar filtro de editora.
- [ ] Aplicar filtro de estilo/gênero e confirmar semântica estrita.
- [ ] Aplicar filtro de literatura/origem.
- [ ] Abrir uma obra e trocar entre edições.
- [ ] Testar busca sem resultado e limpar filtros.
- [ ] Confirmar cadastro manual quando a edição não existir.

## 5. Leitura e estante

Usar um livro de teste identificável e removê-lo ao final.

- [ ] Registrar como `Lendo`.
- [ ] Confirmar que aparece na estante correta.
- [ ] Abrir o detalhe.
- [ ] Alterar status, nota, crítica, privacidade e spoiler.
- [ ] Confirmar persistência após recarregar.
- [ ] Excluir a leitura e confirmar remoção.
- [ ] Verificar que leituras de outros usuários não ficam acessíveis pela sessão atual.

## 6. Diário e progresso

- [ ] Criar entrada por página.
- [ ] Criar entrada por porcentagem ou capítulo.
- [ ] Adicionar anotação privada.
- [ ] Editar entrada.
- [ ] Excluir entrada.
- [ ] Confirmar ordenação e persistência após recarregar.
- [ ] Confirmar que conteúdo privado não aparece em perfil/feed público.

## 7. Conta e autenticação

Executar conexão Google apenas em ambiente/conta de teste apropriados.

- [ ] Abrir perfil anônimo.
- [ ] Conectar conta Google.
- [ ] Confirmar preservação da estante e diário do usuário anônimo.
- [ ] Editar nome, handle, bio e avatar.
- [ ] Confirmar escaping correto de caracteres especiais no perfil público.
- [ ] Sair e entrar novamente quando o fluxo suportar.

## 8. Social

Com duas contas de teste:

- [ ] Tornar uma crítica pública.
- [ ] Localizá-la no Explorar/perfil.
- [ ] Seguir e deixar de seguir.
- [ ] Curtir e remover curtida.
- [ ] Salvar e remover dos salvos.
- [ ] Comentar.
- [ ] Confirmar central de atividade/notificação.
- [ ] Verificar que ações próprias não geram notificação indevida.
- [ ] Testar denúncia sem expor detalhes privados.

## 9. Cards e retrospectiva

- [ ] Abrir card de leitura.
- [ ] Gerar PNG 1080 × 1920.
- [ ] Validar capa real e fallback sem capa.
- [ ] Compartilhar via Web Share API quando disponível.
- [ ] Validar fallback oferecido pelo navegador.
- [ ] Abrir retrospectiva.
- [ ] Navegar por toque/teclado e fechar com Escape.

## 10. PWA

- [ ] Carregar `/manifest.json`.
- [ ] Confirmar ícones PNG e `theme_color`.
- [ ] Instalar a PWA em dispositivo/navegador suportado.
- [ ] Abrir em modo standalone.
- [ ] Confirmar atualização do service worker após nova versão.
- [ ] Verificar comportamento com rede lenta e temporariamente offline.

## 11. Evidência do smoke

Registrar na issue/PR:

- commit testado;
- ambiente e dispositivo/navegador;
- resultado da suíte automatizada;
- itens manuais executados;
- falhas conhecidas não introduzidas pelo PR;
- decisão: aprovado, bloqueado ou rollback.

## Smoke proporcional ao risco

Nem todo PR exige executar manualmente todos os itens. O autor deve selecionar os blocos afetados e justificar no PR. Mudanças de banco, sessão, navegação global ou service worker exigem o checklist completo.
