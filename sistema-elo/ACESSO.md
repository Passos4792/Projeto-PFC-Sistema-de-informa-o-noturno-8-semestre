# Login e cadastro do ELO

## Auditoria

O professor principal acessa **Auditoria** pelo menu lateral (`/auditoria/`). A tela permite filtrar por ação, responsável e datas, com 25 registros por página. Não há rotas de edição ou exclusão do histórico, nem cadastro desse modelo no painel administrativo.

São registrados entrada, saída, falhas e bloqueios de login, respostas de acesso negado (403), criação/edição/exclusão pelos formulários do ELO e pelo painel administrativo dos modelos da aplicação. A criação de usuário registra o perfil concedido; alterações de perfil pelo painel administrativo e a definição de professor principal pelo comando local também são registradas. O comando `ativar_conta` registra a definição/redefinição da senha sem guardar seu valor.

Alterações de cadastro e seus eventos são gravados na mesma transação: se o evento falhar, o cadastro não é alterado. Exclusões impedidas por vínculos não produzem eventos de sucesso. A identificação do autor fica preservada mesmo se sua conta for excluída. Eventos do comando local identificam a origem como “Comando local”, sem atribuí-los a um usuário conectado.

Os registros guardam ação, horário, identificação do responsável, tipo/ID do cadastro e nomes dos campos alterados. Não guardam senhas, tokens, dados clínicos, conteúdo dos formulários ou IPs. Tentativas de login usam uma referência HMAC do nome informado. SQL direto, scripts externos e alterações via shell não são capturados automaticamente; o histórico não é inviolável para quem possui acesso direto ao banco. Regras de retenção serão definidas na etapa de LGPD.

A API externa escolhida para a próxima etapa é o **ViaCEP**, no cadastro de aluno; ainda não foi integrada.

O professor principal cadastra professores, alunos e responsáveis. Professores comuns cadastram alunos e responsáveis. O campo **Nível de acesso** é escolhido no cadastro unificado; não existe escolha de perfil no login. Nenhum cadastro pela interface concede acesso ao painel administrativo do Django ou promove outro professor a principal.

Os professores mantêm acesso aos cadastros e acompanhamentos existentes. Alunos acessam apenas seu painel; responsáveis acessam os painéis dos alunos com vínculo ativo. O cadastro de responsável não cria vínculos automaticamente: use a tela Vínculos.

## Preparação do banco e primeiro acesso

No ambiente Python do projeto, dentro de `sistema-elo`:

```powershell
python manage.py migrate
python manage.py ativar_conta nome.do.professor --principal
python manage.py runserver
```

O comando solicita a senha sem exibi-la. Pode usar o nome de usuário de um professor já cadastrado ou criar o primeiro professor. Não há senha padrão. Abra http://127.0.0.1:8000/login/.

Os cadastros antigos são preservados, sem senha inventada e sem promoção automática. Para ativar o login de um cadastro antigo ou redefinir sua senha, o responsável técnico executa `python manage.py ativar_conta nome.usuario`. As novas contas criadas pelo formulário já recebem senha. O estado ativo/inativo é preservado.

Senhas são armazenadas usando o hash do Django. O botão Esqueci minha senha orienta a procurar o professor principal; envio de e-mail não está implementado. A ativação inicial e redefinições são feitas pelo comando local, sem conceder acesso administrativo ao professor principal.

## Limite de tentativas de login

Após 5 falhas para o mesmo nome de usuário dentro de 15 minutos, novas tentativas ficam bloqueadas por 5 minutos, inclusive com a senha correta. Há também um limite de 20 falhas por IP na mesma janela, com bloqueio de 5 minutos. Tentativas durante o bloqueio não estendem o prazo. Um login bem-sucedido zera as falhas do usuário, mas não as falhas acumuladas pelo IP contra outras contas.

O controle é persistido no banco e compartilhado entre processos do servidor; não depende do navegador. Nomes inexistentes recebem o mesmo tratamento. A tabela não guarda senhas e usa HMAC para as chaves de usuário e IP. Os parâmetros `LOGIN_MAX_FALHAS`, `LOGIN_MAX_FALHAS_IP`, `LOGIN_JANELA_SEGUNDOS` e `LOGIN_BLOQUEIO_SEGUNDOS` ficam em `configuracao/settings.py`.

O IP vem de `REMOTE_ADDR`; cabeçalhos encaminhados pelo navegador não são confiáveis e são ignorados. Caso o sistema seja publicado atrás de proxy, configure a identificação do cliente em uma camada confiável antes de usar o limite por IP. Pessoas que compartilham o mesmo IP compartilham esse limite. O limite por usuário também se aplica ao login do painel Django; o aviso de tempo restante aparece na tela ELO.
