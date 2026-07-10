"""Entrypoint de produção do Lombada.

Sobe o uvicorn lendo a porta da variável de ambiente PORT dentro do Python.

Motivo: o serviço no Railway ficou com um startCommand preso na configuração
(`uvicorn main:app --host 0.0.0.0 --port $PORT`) gravado por um script de
recovery antigo. O Railway passa esse comando como argv, sem shell, então o
`$PORT` chegava literal ao uvicorn ("Invalid value for '--port': '$PORT'") e o
container entrava em crash-loop. Um entrypoint em Python não depende de
expansão de variável por shell: mesmo passado como argv, lê PORT do ambiente.
"""
import os

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
