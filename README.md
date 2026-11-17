# Cobertura e cenários de roteiro

Análise para decidir quantas lojas novas cabem no roteiro de uma equipe de campo sem aumentar a equipe, e quanto cada alavanca abriria de vaga.

## Etapas

| Script | O que faz |
|---|---|
| `01_preparar.py` | Junta a base de lojas com o cadastro do banco e marca quem está sem coordenada |
| `02_geocodificar.py` | Geocodifica o que falta com quatro estratégias em cascata: rua no município, shopping citado no endereço, nome da loja e centro da cidade. Descarta coordenadas a mais de 30 km do centro da cidade declarada. É retomável: grava a cada 20 lojas |
| `03_analisar.py` | Calcula a capacidade de cada promotor (a média de lojas por dia, não o pico) e quais lojas cabem |
| `05_cenarios.py` | Compara cenários de teto por promotor e mostra quantas lojas cada um libera |

## O que vale olhar

- Validação geográfica para pegar geocodificação errada.
- Critério de capacidade conservador e explícito.
- Análise de sensibilidade em vez de um número único.

## Stack

Python, pandas, NumPy, geocodificação via API.

---
Projeto feito no trabalho, publicado sem dados. Os caminhos de arquivo apontam para planilhas internas que não estão no repositório.
