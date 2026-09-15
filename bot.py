def formatar_noticias(dados):
    """
    Formata últimas notícias (apenas se tiver dados válidos)
    """
    ticker = dados["ticker"]
    nome = dados["nome"].split()[0]
    noticias = dados.get("noticias", [])
    
    # Filtra notícias válidas
    noticias_validas = []
    for noticia in noticias:
        titulo = noticia.get('title', '')
        link = noticia.get('link', '')
        publisher = noticia.get('publisher', '')
        
        # Só inclui se tiver título válido e link
        if titulo and titulo.strip() and titulo != 'Sem título' and link and link.startswith('http'):
            noticias_validas.append(noticia)
    
    # Se não tiver notícias válidas, retorna None
    if not noticias_validas:
        return None
    
    msg = f"📰 *NOTÍCIAS - #{ticker} | {nome}*\n\n"
    
    for i, noticia in enumerate(noticias_validas[:3], 1):
        titulo = noticia.get('title', 'Sem título')
        publisher = noticia.get('publisher', 'Desconhecido')
        link = noticia.get('link', '#')
        
        # Trunca título se muito longo
        if len(titulo) > 80:
            titulo = titulo[:77] + "..."
        
        msg += f"{i}. *{titulo}*\n"
        msg += f"   📌 {publisher}\n"
        msg += f"   🔗 [Ler mais]({link})\n\n"
    
    return msg
