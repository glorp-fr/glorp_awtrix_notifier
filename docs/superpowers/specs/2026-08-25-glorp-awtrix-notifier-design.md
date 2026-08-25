# Glorp's Awtrix Notifier — design

Date : 2026-08-25
Repo : https://github.com/glorp-fr/glorp_awtrix_notifier
Domaine HA : `glorp_awtrix_notifier`

## Contexte

Aujourd'hui, l'affichage sur l'écran Awtrix (`awtrix_salon`, seul afficheur physique existant)
passe par ~10 automations HA quasi identiques (`Awtrix - Power usage`, `Awtrix - Solar Power`,
`awtrix_bin`, `Awtrix - Salon Temp`, `awtrix_jardin_temp`, `awtrix_pool`, `awtrix_pluie` +
`awtrix_pluie_remove`, `awtrix_bin_remove`, `Awtrix_lzmmings`, `Awtrix_Ambroisie`,
`Awtrix_sncf` + `Awtrix_sncf_remove`, `awtrix_battery_power`) qui appellent toutes les mêmes
scripts génériques (`script.awtrix_custom`, `script.awtrix_remove` dans `scripts.yaml`),
lesquels publient sur MQTT au format attendu par le firmware Awtrix (topic
`{prefix}/custom/{topic}`, payload JSON `icon`/`text`/`color`/`pushIcon`/`repeat`/`effect`/
`hold`, et `{prefix}/custom/{topic}` avec payload vide pour effacer une app).

Problèmes observés :
- Dupliqué en YAML, pas d'UI de gestion — chaque nouvelle règle veut dire éditer
  `automations.yaml` + `scripts.yaml` à la main.
- Bug trouvé le 2026-08-25 : l'automation `awtrix_battery_power` publie avec
  `prefix: awtrix_battery`, qui ne correspond à aucun afficheur réel (seul `awtrix_salon`
  existe) — le message part sur MQTT mais personne ne l'affiche, sans erreur visible.
- Pas de diagnostic : impossible de voir depuis l'UI si une règle a bien tourné, ce qu'elle a
  décidé, ou pourquoi elle ne s'est pas affichée.

Objectif : remplacer ces automations/scripts par une intégration HACS custom
(`glorp_awtrix_notifier`) où cibles et règles se configurent entièrement depuis l'UI HA, avec
diagnostic par règle. Doit couvrir tous les cas d'usage actuels (y compris les templates Jinja
et la logique de parité semaine du cas poubelle) pour permettre une migration complète.

Hors périmètre de cette spec (projet séparé, à spécifier plus tard) : l'éditeur d'icônes qui
publie dans le référentiel d'icônes Awtrix.

## Approche retenue

**Config Entry Subentries** (API HA native depuis 2024.11 ; VM HAOS en 2026.8.3, largement
compatible). Une seule config entry "Glorp's Awtrix Notifier", avec deux types de sous-entrées
gérées depuis l'UI (menu "···" de l'intégration → Ajouter) :

- **Cible** (`target`) : un afficheur Awtrix — nom convivial + prefix MQTT.
- **Règle** (`rule`) : une notification — déclencheur(s), condition d'affichage, contenu,
  icône, options, cible(s), effacement.

Chaque sous-entrée est éditable/supprimable individuellement dans l'UI, sans toucher YAML.
Alternatives écartées :
- *Options flow avec liste maison* : UX plus pauvre pour ajouter/éditer/supprimer un élément
  d'une liste (pas de widget natif équivalent aux subentries), pas d'entités de diagnostic
  propres par règle.
- *YAML/services* (l'intégration expose juste `glorp_awtrix_notifier.publish`/`.clear`,
  déclenchés par des automations HA classiques) : ne répond pas à l'exigence de configuration
  par UI ; c'est essentiellement le statu quo actuel en un peu plus propre.

Chaque règle (et chaque cible) correspond à un device HA, avec ses propres entités de
diagnostic — même esprit que les sensors `raison_de_la_decision` de `glorp_battery_optimization`.

## Modèle de données (pur, dans `models.py`)

```python
@dataclass
class Target:
    name: str           # nom convivial, ex "Salon"
    mqtt_prefix: str     # ex "awtrix_salon"

class TriggerKind(Enum):
    INTERVAL = "interval"          # toutes les N minutes
    TIME_OF_DAY = "time_of_day"    # heure fixe + jours de semaine
    ENTITY_CHANGE = "entity_change" # changement d'état d'une entité

@dataclass
class Trigger:
    kind: TriggerKind
    # INTERVAL:
    interval_minutes: int | None = None
    # TIME_OF_DAY:
    at: time | None = None
    weekdays: list[str] | None = None   # ["mon", "wed", ...], vide = tous les jours
    # ENTITY_CHANGE:
    entity_id: str | None = None

class ComparisonOp(Enum):
    ABOVE = "above"
    BELOW = "below"
    EQUALS = "equals"

@dataclass
class Condition:
    entity_id: str
    op: ComparisonOp
    value: str | float   # comparé à l'état (cast en float pour above/below)

@dataclass
class Rule:
    name: str
    target_names: list[str]        # référence les Target par nom
    show_triggers: list[Trigger]   # 1+, combinés en OU
    show_condition: Condition | None
    text_template: str             # texte simple ou template Jinja
    icon_template: str             # id/nom fixe ou template Jinja
    color: str = "FFFFFF"
    effect: str = ""
    hold: bool = False
    repeat: int = -1
    clear_triggers: list[Trigger] = field(default_factory=list)
    clear_condition: Condition | None = None
```

`text_template`/`icon_template` sont toujours traités comme des templates Jinja (un texte
simple est juste un template sans expression `{{ }}` — pas de distinction de mode dans l'UI,
juste un champ texte qui accepte du Jinja si besoin, cohérent avec la façon dont HA traite déjà
les templates partout ailleurs).

## Composants

- **`models.py`** — dataclasses ci-dessus, pur, sans dépendance HA.
- **`decision.py`** (pur, testable sans HA installé, comme `decision.py` du projet batterie) —
  fonction `decide(rule, inputs) -> Action` où `inputs` contient les états d'entités déjà résolus
  (dict `entity_id -> str | None`) et l'heure courante. Évalue les conditions (`show_condition`,
  `clear_condition`) et renvoie une des trois actions : `SHOW`, `CLEAR`, `NONE` (ex: entité
  indisponible auquel cas `NONE`, jamais de crash).
- **`publisher.py`** (pur, testable) — `build_show_payload(rule, target, rendered_text,
  rendered_icon) -> (topic, payload_dict)` et `build_clear_payload(rule, target) -> (topic,
  payload_dict_vide)`. Même format JSON que les scripts actuels
  (`icon`/`text`/`color`/`pushIcon`/`repeat`/`effect`/`hold`), topic
  `{target.mqtt_prefix}/custom/{slugify(rule.name)}` — le slug de règle isole chaque règle sur
  son propre "custom app" Awtrix, pas de collision entre règles.
- **`render.py`** (glue HA) — rend `text_template`/`icon_template` via
  `homeassistant.helpers.template.Template(...).async_render()`. Capture toute exception de
  rendu, la remonte comme erreur de règle plutôt que de la laisser remonter et planter le cycle.
- **`triggers.py`** (glue HA) — pour chaque règle active, branche les listeners HA
  correspondant à `show_triggers`/`clear_triggers` :
  - `INTERVAL` → `async_track_time_interval`
  - `TIME_OF_DAY` → `async_track_time_change` (filtré sur les jours dans le callback)
  - `ENTITY_CHANGE` → `async_track_state_change_event`
  Toute entité citée dans `show_condition`/`clear_condition` est aussi suivie en `ENTITY_CHANGE`
  implicite (pour une réactivité immédiate, ex: pluie qui repasse à 0 avant le prochain tick de
  fréquence) — bonus par rapport au comportement actuel (qui ne réagit qu'au polling 5 min).
- **`__init__.py`** — au chargement de la config entry, instancie les `Target`/`Rule` depuis les
  subentries, démarre les listeners `triggers.py` pour chaque règle ; au déchargement, les
  arrête proprement.
- **`config_flow.py`** — flow principal minimal (vérifie juste que l'intégration `mqtt` est
  configurée dans HA, sinon message d'erreur explicite) ; deux subentry flows :
  - `target` : nom + prefix MQTT (validation : prefix non vide, pas déjà utilisé par une autre
    cible)
  - `rule` : nom, cible(s) (multi-select parmi les targets existantes, au moins une requise),
    déclencheur(s) show (1 à 3, formulaire dynamique selon le(s) type(s) coché(s)), condition
    show (optionnelle), texte, icône, couleur/effet/hold/repeat (valeurs par défaut
    pré-remplies), déclencheur(s)/condition clear (optionnels, section repliée par défaut)
- **`sensor.py`** — par règle (device) : `sensor.<rule>_derniere_action` (show/clear/none),
  `sensor.<rule>_raison` (ex: `condition_non_remplie`, `entite_indisponible`,
  `erreur_template:<message>`, `ok`), `sensor.<rule>_dernier_envoi` (timestamp, device_class
  timestamp).

## Flux de données

1. Un listener `triggers.py` se déclenche (intervalle, heure+jour, ou changement d'entité).
2. Le hass component résout les états courants de toutes les entités référencées par la règle
   (condition + templates) en un dict `inputs`.
3. `decision.decide(rule, inputs)` renvoie `SHOW`, `CLEAR` ou `NONE` — logique pure, aucun accès
   I/O.
4. Si `SHOW` : `render.py` rend texte/icône (peut échouer → passe en erreur, `NONE` effectif) ;
   `publisher.build_show_payload` construit le payload pour chaque cible de la règle ;
   `__init__.py` appelle le service `mqtt.publish` pour chacune.
   Si `CLEAR` : idem avec `build_clear_payload`.
   Si `NONE` : rien n'est publié.
5. Les sensors de diagnostic de la règle sont mis à jour dans tous les cas (y compris `NONE`,
   pour que la raison soit visible même quand rien ne se passe).

## Gestion d'erreur

- Entité référencée (condition ou template) indisponible/inconnue → `decide()` renvoie `NONE`,
  raison `entite_indisponible`. Jamais de crash, jamais d'exception qui remonte à HA.
- Échec de rendu de template (`text_template`/`icon_template`) → capturé dans `render.py`,
  raison `erreur_template:<message>`, pas de publication ce cycle.
- Échec d'appel au service `mqtt.publish` (ex: broker MQTT indisponible) → laissé remonter au
  logger HA standard (comportement natif du service, pas de retry maison) ; le sensor
  `dernier_envoi` ne bouge simplement pas.
- Suppression d'une cible référencée par une règle existante → le config flow de suppression de
  cible bloque si des règles y font encore référence (message listant les règles concernées),
  plutôt que de laisser une règle orpheline silencieuse.

## Tests

- `test_decision.py` — toutes les combinaisons déclencheur/condition/action, sans import HA
  (mêmes garanties que `decision.py` du projet batterie : `homeassistant` non installé sur la
  machine de dev, doit rester import-safe).
- `test_publisher.py` — format du payload JSON, construction du topic, cas d'effacement (payload
  vide), slugification du nom de règle.
- Pas de test automatisé pour `render.py`/`triggers.py`/`config_flow.py` (dépendent de HA) — testé
  manuellement sur la VM HAOS comme pour le projet batterie.

## Migration des automations existantes

Cas couverts par le modèle (à migrer un par un après implémentation, en gardant l'automation
YAML jusqu'à validation de l'équivalent en règle) :

| Automation actuelle | Règle équivalente |
|---|---|
| `Awtrix - Power usage`, `Awtrix - Solar Power`, `Awtrix - Salon Temp` | 1 trigger `INTERVAL` 5 min, pas de condition, texte = valeur d'entité |
| `awtrix_bin` + `awtrix_bin_remove` | show : `TIME_OF_DAY` 01:00 lun/mar/mer ; clear : `TIME_OF_DAY` 01:00 jeu/ven/sam/dim ; icône = template Jinja parité semaine |
| `awtrix_jardin_temp`, `awtrix_pool` | 1 trigger `ENTITY_CHANGE` + condition seuil (above) |
| `awtrix_pluie` + `awtrix_pluie_remove` | show : `INTERVAL` 5 min + condition `above 0` sur l'entité pluie (et `ENTITY_CHANGE` implicite sur cette même entité pour réactivité immédiate) ; clear : `TIME_OF_DAY` 00:01 |
| `Awtrix_lzmmings`, `Awtrix_Ambroisie` | 1 trigger `INTERVAL`/`TIME_OF_DAY`, texte simple ou template |
| `Awtrix_sncf` + `Awtrix_sncf_remove` | show : `TIME_OF_DAY` 07:15, texte = template Jinja if/else existant, tel quel |
| `awtrix_battery_power` (buggée) | 1 trigger `INTERVAL` 5 min, cible = "Salon" (le seul afficheur réel) — corrige le bug de prefix par construction |

## Hors périmètre

- Éditeur d'icônes / publication dans le référentiel Awtrix (spec séparée, projet indépendant).
- Migration automatique des automations existantes (fait manuellement, une par une, après
  validation de l'intégration).
- Support d'un second afficheur Awtrix physique (l'architecture le permet nativement via
  plusieurs `Target`, mais il n'y en a qu'un seul aujourd'hui — rien à développer spécifiquement).
