"""Restaura reservas e autorizações iniciais sem alterar os arquivos-fonte."""

import argparse

from residencial_aurora.storage import restore_initial_data


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", help="Caminho SQLite (padrão: DATABASE_PATH ou data/residencial_aurora.sqlite3)")
    args = parser.parse_args()
    restore_initial_data(args.database)
    print("Dados iniciais de apartamentos, áreas, reservas e visitantes restaurados.")
    print("Sessões, eventos e pendências foram preservados.")


if __name__ == "__main__":
    main()
