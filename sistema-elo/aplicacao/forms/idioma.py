from django import forms


def traduzir_opcoes(formulario):
    for campo in formulario.fields.values():
        if isinstance(campo, forms.ModelChoiceField) and campo.empty_label is not None:
            if str(campo.empty_label) in ('---------', '- Select an option -', 'Select an option'):
                campo.empty_label = 'Selecione uma opção' if campo.required else 'Não definido'
