# TP — Cluster Cassandra : réplication et tolérance aux pannes

## M2 Big Data & IA — Données distribuées

**Travail :** individuel  
**Technologies :** Apache Cassandra · Docker · Docker Compose · CQL  
**Sujet :** les données et la table métier créées lors du TP2

---

## 1. Objectif

Dans le TP précédent, vous avez créé et manipulé une **table métier dans Cassandra** à partir des données de votre sujet.

Dans ce TP, vous allez utiliser cette même table dans un **cluster Cassandra à 3 nœuds** afin d'observer concrètement :

- la distribution des données ;
- la réplication ;
- le `Replication Factor` ;
- les niveaux de cohérence ;
- le comportement du cluster lorsqu'un nœud tombe en panne ;
- le retour du nœud après redémarrage.

> **Important :** vous ne devez pas recréer les données avec un nouvel exemple.
>
> Vous utilisez **la table métier créée lors du TP2** et les données déjà préparées dans votre projet.

---

## 2. Architecture du cluster

Le cluster sera composé de trois nœuds :

```text
                 Cluster Cassandra
                       │
                      dc1
                       │
          ┌────────────┼────────────┐
          │            │            │
        rack1        rack2        rack3
          │            │            │
        cass4        cass5        cass6
```

Les nœuds seront démarrés progressivement :

```text
cass4
  ↓
cass4 + cass5
  ↓
cass4 + cass5 + cass6
```

---

## 3. Mise en place du cluster

Utilisez le fichier `docker-compose.yml` fourni dans le cadre du TP / projet.

Le cluster doit utiliser :

```text
Cluster : tp2-cluster
Datacenter : dc1
Nœuds : cass4, cass5, cass6
Racks : rack1, rack2, rack3
```

Démarrez les nœuds **un par un**.

Après chaque démarrage, vérifiez l'état du cluster avec `nodetool status`.

### Question 1

Après le démarrage des trois nœuds :

- **Nombre de nœuds :** trois (`cass4`, `cass5` et `cass6`).
- **État attendu après leur démarrage complet :** `UN` (*Up/Normal*) pour chacun.
- **Datacenter :** `dc1`.
- **Racks :** `cass4` dans `rack1`, `cass5` dans `rack2` et `cass6` dans `rack3`.

À confirmer via `nodetool status` (un nœud peut passer brièvement par `UJ` avant `UN`).

---

## 4. Vérifier le cluster

Lorsque les trois nœuds sont opérationnels, observez la configuration du cluster.

Vérifiez notamment :

- **Nom :** `tp2-cluster`.
- **Nœuds :** trois.
- **Datacenter :** `dc1`.
- **Racks :** `rack1`, `rack2` et `rack3`.
- **État attendu une fois le démarrage terminé :** les trois nœuds sont `UN`.

### Question 2

**Architecture :** `cass4`, `cass5`, `cass6` appartiennent au cluster `tp2-cluster`, datacenter `dc1`, répartis sur `rack1`/`rack2`/`rack3`. État final attendu : `UN` partout.

**Différences :** cluster = ensemble de nœuds coopérants ; datacenter = subdivision logique (site/région) ; rack = subdivision du datacenter servant à isoler les domaines de panne pour la réplication ; nœud = instance Cassandra individuelle.

---

## 5. Utiliser la table métier du TP2

Vous devez maintenant réutiliser **la table métier créée lors du TP2**.

Ne créez pas une nouvelle table d'exemple.

Vérifiez que :

- le keyspace existe ;
- la table métier existe ;
- les données du TP2 sont accessibles.

### Question 3

**Keyspace :** `birds`. **Table principale :** `observations` (`observation_id` bigint, `common_name`, `scientific_name`, `observed_on` date, `latitude`/`longitude` double ; clé primaire simple = `observation_id`, pas de clustering).

Le projet ajoute des tables de requête dénormalisées pour d'autres accès : `observations_by_date` (partition `observed_on`, clustering `observation_id`), `observations_by_species` (partition `scientific_name`, clustering `observed_on`, `observation_id`), `observations_by_species_date` et `observations_by_common_name` suivent le même principe.

---

## 6. Configurer la réplication

Votre keyspace doit utiliser une stratégie adaptée à un cluster Cassandra réparti sur plusieurs nœuds.

Configurez une réplication avec :

```text
Datacenter : dc1
Replication Factor : 3
```

### Question 4

**RF = 3** = trois copies totales de chaque partition dans `dc1` (pas une copie + trois), réparties entre les nœuds en tenant compte des racks.

**Partitionnement** = placement d'une partition selon sa clé/token. **Réplication** = copies supplémentaires de cette partition sur d'autres nœuds, pour la disponibilité et la tolérance aux pannes.

**⚠️ Piège du projet :** `.env` a `CASSANDRA_REPLICATION_FACTOR=1` et le code crée le keyspace en `SimpleStrategy`. Il faut corriger avant les tests :

```sql
ALTER KEYSPACE birds
WITH replication = {'class': 'NetworkTopologyStrategy', 'dc1': 3}
AND durable_writes = true;
```

Vérification dans `cqlsh` :

```text
DESCRIBE KEYSPACE birds;
```

Il est préférable de régler la réplication avant de charger les données. Si des données ont déjà été écrites avec l'ancien facteur, lancer une réparation Cassandra sur les nœuds permet de propager les réplicas selon la nouvelle stratégie avant les tests de panne.

---

## 7. Vérifier la distribution

Observez l'état du cluster après la configuration de la réplication.

Utilisez les outils Cassandra disponibles pour observer :

- les nœuds ;
- les tokens ;
- la répartition du cluster.

### Question 5

Expliquez brièvement le chemin suivant pour une donnée de votre table métier :

```text
Partition key
      ↓
Hash
      ↓
Token
      ↓
Nœud(s) responsable(s)
      ↓
Réplicas
```

**Réponse :** `observation_id` (clé de partition) → hachage Murmur3 → token → nœud propriétaire de la plage de tokens → avec RF=3 dans `dc1`, trois réplicas au total répartis en tenant compte des racks. Lectures/écritures sont servies par ces réplicas selon le niveau de cohérence demandé.

> Les tables secondaires ont d'autres clés de partition : `observed_on` pour `observations_by_date`, `scientific_name` pour `observations_by_species`.

---

## 8. Tester les niveaux de cohérence

Avec :

```text
RF = 3
```

testez successivement les niveaux :

```text
ONE
QUORUM
ALL
```

Pour chaque niveau, exécutez une lecture sur **une donnée réelle de votre table métier**.

### Question 6

Comparez les trois niveaux :

| Niveau | Réplicas nécessaires avec RF=3 |
|---|---:|
| ONE | 1 |
| QUORUM | 2 |
| ALL | 3 |

**Réponse :** `ONE` = 1 réplica répond : le plus rapide et disponible, mais peut renvoyer une valeur pas encore à jour. `QUORUM` = majorité (2/3) : compromis disponibilité/cohérence. `ALL` = les 3 réplicas : le plus strict, échoue dès qu'un nœud manque. En lecture **et** écriture au niveau `QUORUM`, les ensembles de réplicas se recoupent toujours, ce qui garantit de lire la dernière valeur écrite.

---

## 9. Simuler une panne

Vous allez maintenant simuler la panne d'un nœud.

Arrêtez :

```text
cass6
```

Vérifiez ensuite l'état du cluster.

Vous devez constater que :

```text
cass4 → disponible
cass5 → disponible
cass6 → indisponible
```

### Question 7

**Réponse attendue :** `nodetool status` : `cass4`/`cass5` en `UN`, `cass6` en `DN` (down). 2 nœuds disponibles sur 3 (détection pouvant prendre un court délai).

---

## 10. Tester les données pendant la panne

La table métier doit toujours être utilisée pour les tests.

Réalisez à nouveau une lecture avec :

```text
ONE
QUORUM
ALL
```

Utilisez les **mêmes données métier** que précédemment afin de comparer les résultats.

### Question 8

**Réponse attendue avec RF = 3 :** `ONE` et `QUORUM` réussissent (1 et 2 réponses suffisent avec les 2 nœuds restants). `ALL` échoue (`UnavailableException`), car les 3 réplicas sont exigés et `cass6` est arrêté.

Le principe est :

```text
Nombre de réplicas disponibles >= nombre requis par le Consistency Level
```

---

## 11. Redémarrer le nœud

Redémarrez ensuite :

```text
cass6
```

Vérifiez son retour dans le cluster.

Observez à nouveau l'état des trois nœuds.

### Question 9

**Réponse attendue :** oui, `cass6` rejoint le cluster (`UJ` puis `UN`). Le volume Docker persistant lui conserve ses données locales ; les écritures manquées sont rattrapées via hints/réparation.

---

## 12. Vérifier la réplication après redémarrage

Une fois les trois nœuds revenus dans un état normal, vérifiez à nouveau les données de votre **table métier**.

Effectuez plusieurs lectures sur des données existantes.

L'objectif est de constater que les données restent accessibles et que le cluster a conservé le mécanisme de réplication.

### Question 10

chaque ligne est répliquée 3 fois (RF=3). Pendant la panne de `cass6`, les 2 autres réplicas servent les lectures si le CL est satisfait. Au redémarrage, `cass6` revient en `UN` et les données restent accessibles sur l'ensemble des réplicas — à confirmer par des lectures plutôt que supposer une synchronisation instantanée.

Votre réponse doit expliquer simplement :

```text
Donnée
   ↓
Partition
   ↓
Réplication
   ↓
Panne d'un nœud
   ↓
Données toujours accessibles
   ↓
Retour du nœud
```

---

## 13. Synthèse

À partir de votre table métier, expliquez en quelques lignes le scénario réalisé :

```text
3 nœuds (`cass4`, `cass5`, `cass6`)
   ↓
RF = 3
   ↓
Données répliquées
   ↓
Arrêt de cass6
   ↓
2 nœuds disponibles
   ↓
Tests ONE / QUORUM / ALL
   ↓
Redémarrage de cass6
   ↓
Retour du nœud
   ↓
Vérification des données
```

### Question 11

**Réponse :** la réplication maintient plusieurs copies d'une partition sur des nœuds différents, ce qui laisse les requêtes aboutir tant que le `Consistency Level` demandé est satisfaisable. Avec RF=3 et un nœud arrêté, `ONE` et `QUORUM` restent possibles, `ALL` non : la tolérance aux pannes dépend du RF, du placement des réplicas et du CL choisi — pas d'un seul de ces facteurs.

---

## 14. Livrable

Le rendu est **individuel**.

Vous devez fournir votre dépôt Git contenant :

```text
TP-Cassandra-Cluster/
│
├── docker-compose.yml
├── README.md
└── docs/
    └── compte-rendu.md
```

Le `compte-rendu.md` doit contenir :

- l'architecture du cluster ;
- votre table métier du TP2 ;
- le `Replication Factor` ;
- les tests `ONE`, `QUORUM`, `ALL` ;
- la simulation de panne ;
- le redémarrage de `cass6` ;
- vos observations et conclusions.

Ajoutez les captures d'écran importantes permettant de prouver les étapes réalisées :

```text
1. Cluster avec 3 nœuds
2. Table métier et données
3. Tests de cohérence
4. Panne de cass6
5. Résultats pendant la panne
6. Retour de cass6
7. Vérification finale des données
```

---

## 15. Nettoyage

À la fin du TP, arrêtez le cluster avec la commande prévue dans votre projet.

Si vous souhaitez supprimer également les volumes Cassandra du projet, utilisez l'option permettant de supprimer les volumes.

> Attention : la suppression des volumes entraîne la suppression des données Cassandra stockées dans ces volumes.

---

## Conclusion

L'objectif de ce TP est de passer d'une **table Cassandra fonctionnelle** à une compréhension concrète de son fonctionnement distribué.

Vous devez retenir la chaîne :

```text
Table métier
     ↓
Partitionnement
     ↓
Réplication
     ↓
Replication Factor
     ↓
Consistency Level
     ↓
Panne d'un nœud
     ↓
Tolérance aux pannes
     ↓
Retour du nœud
```

Le point essentiel est de constater expérimentalement que **les données de votre table métier sont répliquées sur plusieurs nœuds et restent accessibles selon le niveau de cohérence demandé lorsqu'un nœud devient indisponible**.
