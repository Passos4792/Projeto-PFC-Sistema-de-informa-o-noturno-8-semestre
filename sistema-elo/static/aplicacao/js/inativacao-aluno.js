document.addEventListener('DOMContentLoaded', () => {
  const ativo = document.getElementById('id_ativo');
  const aviso = document.getElementById('aviso-arquivo-inativo');
  if (!ativo || !aviso) return;
  const atualizar = () => { aviso.hidden = ativo.checked; };
  ativo.addEventListener('change', atualizar);
  atualizar();
});
