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

Ces états sont à confirmer dans la sortie réelle de `nodetool status` ; pendant le démarrage, un nœud peut temporairement apparaître en `UJ` (*Up/Joining*).

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

**Architecture :** les trois nœuds `cass4`, `cass5` et `cass6` appartiennent au cluster `tp2-cluster` et au datacenter `dc1`. Ils sont configurés dans trois racks distincts (`rack1`, `rack2`, `rack3`). Une fois le démarrage terminé, l'état attendu de chaque nœud est `UN`.

**Différences :**

```text
Cluster : ensemble de nœuds Cassandra qui coopèrent pour stocker et gérer les données.
Datacenter : subdivision logique du cluster, souvent associée à une région ou à un site.
Rack : subdivision logique du datacenter, utilisée notamment pour répartir les réplicas entre domaines de panne.
Nœud : instance Cassandra individuelle participant au cluster.
```

---

## 5. Utiliser la table métier du TP2

Vous devez maintenant réutiliser **la table métier créée lors du TP2**.

Ne créez pas une nouvelle table d'exemple.

Vérifiez que :

- le keyspace existe ;
- la table métier existe ;
- les données du TP2 sont accessibles.

### Question 3

**Keyspace :** `birds`.  
**Table principale :** `observations`. Le projet crée également des tables de requête (`observations_by_date`, `observations_by_species`, `observations_by_species_date` et `observations_by_common_name`).

Dans `observations`, les colonnes sont `observation_id` (`bigint`), `common_name` (`text`), `scientific_name` (`text`), `observed_on` (`date`), `latitude` (`double`) et `longitude` (`double`). La clé primaire est `observation_id` : c'est une clé de partition simple. Cette table n'a pas de clé de clustering.

Les clés des tables de requête diffèrent : par exemple, `observations_by_date` a `observed_on` comme clé de partition et `observation_id` comme clé de clustering ; `observations_by_species` a `scientific_name` comme clé de partition et `observed_on`, puis `observation_id`, comme clés de clustering.

---

## 6. Configurer la réplication

Votre keyspace doit utiliser une stratégie adaptée à un cluster Cassandra réparti sur plusieurs nœuds.

Configurez une réplication avec :

```text
Datacenter : dc1
Replication Factor : 3
```

### Question 4

**RF = 3** signifie que Cassandra conserve trois copies de chaque partition dans le datacenter configuré. Il s'agit de trois copies au total, pas d'une copie plus trois autres. Dans ce cluster, les copies sont réparties entre les nœuds, en tenant compte des racks.

Le **partitionnement** découpe et distribue les données selon la clé de partition et le token correspondant : il détermine où une partition est placée. La **réplication** crée des copies de cette partition sur d'autres nœuds, afin d'améliorer la disponibilité et la tolérance aux pannes.

**Attention à la configuration du projet :** pour les tests du TP, le keyspace `birds` doit effectivement être configuré en `NetworkTopologyStrategy` avec `dc1: 3`. La configuration `.env` actuelle indique `CASSANDRA_REPLICATION_FACTOR=1` et le code crée un keyspace en `SimpleStrategy` si celui-ci n'existe pas. Il faut donc vérifier/corriger le keyspace avant les essais, par exemple avec :

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

**Réponse :** Dans la table `birds.observations`, la clé primaire est `observation_id` ; elle est donc aussi la clé de partition. Cassandra applique sa fonction de hachage (Murmur3 par défaut) à cette valeur pour obtenir un token. Ce token situe la partition dans l’anneau et détermine la plage de tokens qui la contient. Le nœud propriétaire de cette plage est identifié comme premier responsable. Avec un facteur de réplication de 3 dans `dc1`, Cassandra stocke au total trois copies de la partition sur des nœuds du datacenter, en tenant compte de la topologie des racks. Les lectures et écritures peuvent alors être servies par ces réplicas selon le niveau de cohérence demandé.

> Pour les tables secondaires, la clé de partition dépend de leur définition : par exemple `observations_by_date` est partitionnée par `observed_on`, tandis que `observations_by_species` l’est par `scientific_name`.

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

**Réponse :** `ONE` demande une réponse d'au moins un réplica : c'est le niveau le plus disponible et le plus rapide, mais la réponse peut ne pas refléter immédiatement une écriture récente si les réplicas ne sont pas encore synchronisés. `QUORUM` demande une majorité, soit deux réplicas sur trois ; il offre un compromis entre disponibilité et cohérence. `ALL` demande les trois réplicas : il fournit la vérification la plus stricte, mais échoue dès qu'un réplica est indisponible. Avec des lectures et écritures toutes deux au niveau `QUORUM`, les ensembles se recoupent, ce qui favorise la lecture de la dernière valeur écrite.

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

**Réponse attendue :** `nodetool status` indique deux nœuds `UN` (`cass4` et `cass5`) et un nœud indisponible (`cass6`, normalement signalé `DN`). Il reste donc deux nœuds disponibles sur trois. Le résultat exact doit être confirmé avec la commande, car Cassandra peut mettre un court délai à détecter la panne.

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

**Réponse attendue avec RF = 3 :** les lectures `ONE` et `QUORUM` peuvent réussir avec deux nœuds disponibles : elles nécessitent respectivement une et deux réponses. La lecture `ALL` échoue, car elle exige les trois réplicas et `cass6` est arrêté. `RF = 3` laisse donc deux copies accessibles pendant cette panne, mais ne permet pas de satisfaire une opération qui exige les trois copies. Il faut exécuter les tests avec les mêmes lignes et préciser que les résultats dépendent aussi du fait que ces partitions possèdent bien leurs réplicas sur les nœuds attendus.

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

**Réponse attendue :** oui, `cass6` rejoint à nouveau le cluster. Pendant son démarrage, il peut apparaître temporairement `UJ` (*Up/Joining*), puis passer à `UN` (*Up/Normal*) lorsque le nœud a rejoint le ring. Le volume Docker persistant permet au nœud de retrouver ses données locales ; Cassandra peut ensuite rattraper les écritures manquées selon les mécanismes de hints et de réparation.

---

## 12. Vérifier la réplication après redémarrage

Une fois les trois nœuds revenus dans un état normal, vérifiez à nouveau les données de votre **table métier**.

Effectuez plusieurs lectures sur des données existantes.

L'objectif est de constater que les données restent accessibles et que le cluster a conservé le mécanisme de réplication.

### Question 10

chaque ligne appartient à une partition déterminée par sa clé de partition. Avec RF = 3, Cassandra conserve trois réplicas de cette partition. Lorsque `cass6` tombe en panne, les autres nœuds peuvent encore servir les lectures si le niveau de cohérence demandé est satisfait. À son redémarrage, `cass6` rejoint le cluster et revient normalement à l'état `UN`; les données redeviennent disponibles auprès de l'ensemble des réplicas. Il faut vérifier les données avec des lectures et confirmer l'état des nœuds plutôt que supposer qu'une synchronisation complète est instantanée.

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

**Réponse :** la réplication conserve plusieurs copies d'une même partition sur des nœuds différents. Si un nœud tombe en panne, les autres réplicas peuvent continuer à répondre aux requêtes dont le niveau de cohérence peut être satisfait. La disponibilité dépend donc du nombre de réplicas encore joignables et du `Consistency Level` : avec RF = 3 et un seul nœud arrêté, `ONE` et `QUORUM` restent possibles, tandis que `ALL` ne l'est plus. La réplication améliore la tolérance aux pannes, mais ne garantit pas que tous les niveaux de cohérence réussiront pendant une panne.

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
