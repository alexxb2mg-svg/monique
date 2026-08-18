import actions
import roles


def test_role_defaut_non_vide():
    assert "secrétaire" in roles.charger("secretaire").lower()


def test_action_masquee_si_check_faux():
    actions.registre.clear()
    actions.enregistrer(
        actions.Action(
            "envoyer", "envoie", handler=lambda **k: None, check_fn=lambda: False
        )
    )
    actions.enregistrer(actions.Action("copier", "copie", handler=lambda **k: None))
    noms = [a.nom for a in actions.disponibles()]
    assert "copier" in noms and "envoyer" not in noms
