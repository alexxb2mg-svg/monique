from datetime import datetime

from entrepot import connexion_ecriture


def definir(cle, valeur, chemin=None):
    con = connexion_ecriture(chemin)
    try:
        con.execute(
            "INSERT OR REPLACE INTO secw_parametres(cle, valeur, maj_le) VALUES(?,?,?)",
            (cle, valeur, datetime.now().isoformat()),
        )
        con.commit()
    finally:
        con.close()


def lire(cle, chemin=None):
    con = connexion_ecriture(chemin)
    try:
        r = con.execute(
            "SELECT valeur FROM secw_parametres WHERE cle=?", (cle,)
        ).fetchone()
        return r["valeur"] if r else None
    finally:
        con.close()
