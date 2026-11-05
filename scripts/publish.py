#!/usr/bin/env python3
"""XII News : publie l'édition du jour sur Instagram avec l'API officielle (connexion Instagram).

Usage : python3 scripts/publish.py <dossier_visuels> <url_publique_du_dossier> <AAAA-MM-JJ>

Variables d'environnement :
  IG_ACCESS_TOKEN  jeton Instagram (obligatoire pour publier ; sans lui, simple essai à blanc)
  DRY_RUN=1        vérifie tout sans rien publier
  FORCE=1          republie même si l'édition est marquée comme déjà publiée
  IG_API_VERSION   version de l'API, ex. v23.0 (facultatif ; v23.0 par défaut côté Facebook)
  IG_USER_ID       identifiant du compte Instagram (facultatif, trouvé automatiquement)

Deux sortes de jetons sont acceptées :
  - jeton « connexion Instagram » (commence par IGAA) -> graph.instagram.com
  - jeton Meta « connexion unifiée » ou « connexion Facebook » (utilisateur système, utilisateur
    ou Page) -> graph.facebook.com ; le compte Instagram est retrouvé via la Page liée.

Ordre : le carrousel d'abord (sommaire + 12 infos), puis les 12 stories.
L'avancement est noté dans published/<date>.json après chaque étape : si le robot s'arrête
en route, le relancer reprend là où il s'était arrêté, sans rien publier deux fois.
"""
import json, os, sys, time
import requests

TOKEN = os.environ.get("IG_ACCESS_TOKEN", "").strip()
DRY = os.environ.get("DRY_RUN") == "1" or not TOKEN
FORCE = os.environ.get("FORCE") == "1"
VER = os.environ.get("IG_API_VERSION", "").strip()
IG_LOGIN = TOKEN.startswith("IGA")
if IG_LOGIN:
    API = "https://graph.instagram.com/" + (VER + "/" if VER else "")
else:
    API = "https://graph.facebook.com/" + (VER or "v23.0") + "/"
FIXED_ID = os.environ.get("IG_USER_ID", "").strip()


class IGError(Exception):
    pass


def call(method, path, **params):
    params["access_token"] = TOKEN
    for attempt in range(4):
        try:
            r = requests.request(method, API + path, params=params if method == "GET" else None,
                                 data=params if method == "POST" else None, timeout=60)
        except requests.RequestException as e:
            err = str(e)
        else:
            body = r.json() if r.content else {}
            if r.ok and "error" not in body:
                return body
            e = body.get("error", {})
            err = f"{r.status_code} {e.get('type', '')} code={e.get('code')} {e.get('message', r.text[:300])}"
            transient = r.status_code >= 500 or e.get("is_transient") or e.get("code") in (1, 2, 4, 17, 32, 613)
            if not transient:
                raise IGError(err)
        wait = 10 * (attempt + 1)
        print(f"  erreur passagère ({err}), nouvel essai dans {wait} s")
        time.sleep(wait)
    raise IGError(err)


def find_account():
    """Renvoie (identifiant Instagram, @nom) quel que soit le type de jeton."""
    if FIXED_ID:
        info = call("GET", FIXED_ID, fields="username")
        return FIXED_ID, info.get("username", "?")
    if IG_LOGIN:
        me = call("GET", "me", fields="user_id,username")
        return me.get("user_id") or me.get("id"), me.get("username")
    # Jeton de Page : la Page elle-même porte le compte Instagram
    try:
        me = call("GET", "me", fields="instagram_business_account{id,username}")
        acc = me.get("instagram_business_account")
        if acc:
            return acc["id"], acc.get("username")
    except IGError:
        pass
    # Jeton utilisateur ou utilisateur système : on parcourt ses Pages
    pages = call("GET", "me/accounts", fields="name,instagram_business_account{id,username}").get("data", [])
    for pg in pages:
        acc = pg.get("instagram_business_account")
        if acc:
            return acc["id"], acc.get("username")
    raise IGError("aucun compte Instagram professionnel trouvé avec ce jeton. Vérifie que @xii.news est bien "
                  "relié (Page Facebook ou portefeuille business) et que les autorisations de publication sont accordées.")


def wait_ready(container_id, label):
    for _ in range(60):
        st = call("GET", container_id, fields="status_code,status").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise IGError(f"Instagram a refusé {label} (statut {st}). Vérifie que l'image est un JPEG accessible publiquement.")
        time.sleep(3)
    raise IGError(f"{label} : Instagram n'a pas fini de traiter l'image après 3 minutes")


def publish_container(ig_id, container_id):
    for _ in range(5):
        try:
            return call("POST", f"{ig_id}/media_publish", creation_id=container_id)["id"]
        except IGError as e:
            if "9007" in str(e) or "not ready" in str(e).lower():
                time.sleep(5)
                continue
            raise
    raise IGError("publication refusée : le contenu n'était toujours pas prêt")


def main():
    folder, base_url, date = sys.argv[1], sys.argv[2].rstrip("/"), sys.argv[3]
    man = json.load(open(os.path.join(folder, "manifest.json"), encoding="utf-8"))
    os.makedirs("published", exist_ok=True)
    state_path = os.path.join("published", f"{date}.json")
    state = json.load(open(state_path)) if os.path.exists(state_path) else {}
    if FORCE:
        state = {}
    if state.get("done"):
        print(f"Édition {date} déjà publiée ({state.get('permalink', '')}). Rien à faire. Utilise FORCE pour republier.")
        return

    def save():
        json.dump(state, open(state_path, "w"), indent=1)

    url = lambda f: f"{base_url}/{f}"
    print(f"Édition {date} : {len(man['carousel'])} images de carrousel, {len(man['stories'])} stories")
    for f in man["carousel"] + man["stories"]:
        r = requests.head(url(f), timeout=30, allow_redirects=True)
        if r.status_code != 200:
            raise SystemExit(f"Image introuvable en ligne : {url(f)} (HTTP {r.status_code})")
    print("Toutes les images sont en ligne.")

    if DRY:
        why = "DRY_RUN=1" if TOKEN else "aucun jeton IG_ACCESS_TOKEN configuré"
        if TOKEN:
            _, uname = find_account()
            print(f"Jeton valide : connecté au compte @{uname}.")
        print(f"ESSAI À BLANC ({why}) : rien n'est publié.")
        print("Légende :\n" + man["caption"])
        return

    ig_id, uname = find_account()
    print(f"Compte : @{uname} ({ig_id})")

    # 1) carrousel
    if not state.get("carousel_id"):
        children = []
        for i, f in enumerate(man["carousel"], 1):
            c = call("POST", f"{ig_id}/media", image_url=url(f), is_carousel_item="true")["id"]
            children.append(c)
            print(f"  image {i}/{len(man['carousel'])} envoyée")
        for i, c in enumerate(children, 1):
            wait_ready(c, f"l'image {i} du carrousel")
        parent = call("POST", f"{ig_id}/media", media_type="CAROUSEL", children=",".join(children),
                      caption=man["caption"])["id"]
        wait_ready(parent, "le carrousel")
        state["carousel_id"] = publish_container(ig_id, parent)
        try:
            state["permalink"] = call("GET", state["carousel_id"], fields="permalink").get("permalink", "")
        except IGError:
            pass
        save()
        print(f"Carrousel publié : {state.get('permalink', state['carousel_id'])}")
    else:
        print("Carrousel déjà publié, on passe aux stories.")

    # 2) stories
    done = state.setdefault("stories", [])
    for i, f in enumerate(man["stories"]):
        if i < len(done):
            continue
        c = call("POST", f"{ig_id}/media", media_type="STORIES", image_url=url(f))["id"]
        wait_ready(c, f"la story {i + 1}")
        done.append(publish_container(ig_id, c))
        save()
        print(f"  story {i + 1}/{len(man['stories'])} publiée")
        time.sleep(2)

    state["done"] = True
    state["published_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save()
    print(f"Terminé : 1 carrousel + {len(done)} stories publiés sur @{uname}.")


if __name__ == "__main__":
    try:
        main()
    except IGError as e:
        raise SystemExit(f"Échec de la publication : {e}")
