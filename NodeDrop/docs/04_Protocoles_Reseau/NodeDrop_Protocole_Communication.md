NodeDrop — Protocole de communication (V1)
1. Objet du document

Ce document définit le protocole de communication utilisé par NodeDrop pour la version 1.

Il décrit :

les mécanismes de découverte des machines

l’établissement d’une connexion

l’authentification

les échanges de messages

le transfert de fichiers

Le protocole est conçu pour fonctionner sur un réseau local (LAN) et permettre une communication fiable entre deux instances NodeDrop.

2. Types de communication

NodeDrop utilise deux types de communication réseau :

Type	Protocole	Usage
Découverte réseau	UDP	Détection des machines
Connexion / transfert	TCP	Communication fiable
3. Ports utilisés

Les ports par défaut seront :

UDP Discovery : 48555
TCP Communication : 48556

Ces ports pourront être configurables dans une version future.

3.1 Séparation configuration / protocole

Les constantes du protocole et les paramètres de configuration de l’application doivent être séparés dans le code.

Deux catégories de constantes existent :

Configuration applicative

Ces constantes peuvent être modifiées selon l’environnement :

ports réseau
intervalle d’annonce UDP
taille des blocs de transfert
chemins des journaux
timeouts réseau

Ces valeurs doivent être définies dans :

utils/config.py

Constantes du protocole

Ces constantes définissent la structure du protocole NodeDrop et ne doivent pas être modifiées sans modifier la compatibilité réseau.

Exemples :

NODE_ANNOUNCE
SESSION_REQUEST
SESSION_ACCEPTED
AUTH_REQUEST
TRANSFER_INIT
FILE_INFO

Ces constantes doivent être centralisées dans :

network/protocol.py

Cette séparation permet d’éviter que config.py devienne un fichier mélangeant logique réseau et configuration applicative.

4. Découverte des machines
4.1 Principe

Chaque instance NodeDrop :

diffuse périodiquement un message UDP sur le réseau local

écoute les messages envoyés par les autres instances

Cela permet aux machines de se détecter automatiquement.

4.2 Fréquence d’annonce

Chaque instance envoie un message de présence toutes les :

5 secondes
4.3 Format du message de découverte

Le message est envoyé en UDP broadcast.

Format JSON :

{
  "type": "NODE_ANNOUNCE",
  "node_id": "123e4567",
  "node_name": "Alex-PC",
  "ip": "192.168.1.24",
  "port": 48556,
  "status": "available"
}
4.4 Champs du message
Champ	Description
type	Type de message
node_id	Identifiant unique NodeDrop
node_name	Nom de la machine
ip	Adresse IP locale
port	Port TCP d’écoute
status	État de la machine
4.5 États possibles
available
busy
offline
5. Établissement d'une connexion

Lorsqu’un utilisateur souhaite se connecter à une machine distante, une connexion TCP est ouverte.

5.1 Séquence de connexion

Machine A sélectionne machine B

Machine A ouvre une connexion TCP vers B

Machine A envoie une demande de session

Machine B demande confirmation à l’utilisateur

Machine B accepte ou refuse

6. Message de demande de connexion

Message envoyé par la machine initiatrice :

{
  "type": "SESSION_REQUEST",
  "node_id": "123e4567",
  "node_name": "Alex-PC"
}
7. Réponse à la demande
Acceptation
{
  "type": "SESSION_ACCEPTED"
}
Refus
{
  "type": "SESSION_REJECTED"
}
8. Authentification

Après acceptation de la connexion, une authentification est requise.

8.1 Demande de mot de passe

Machine A :

{
  "type": "AUTH_REQUEST"
}
8.2 Envoi du mot de passe

Machine B :

{
  "type": "AUTH_RESPONSE",
  "password": "mot_de_passe"
}
8.3 Résultat de l'authentification
Succès
{
  "type": "AUTH_SUCCESS"
}
Échec
{
  "type": "AUTH_FAILED"
}
9. Préparation du transfert

Avant le transfert réel, les métadonnées sont envoyées.

9.1 Message de préparation
{
  "type": "TRANSFER_INIT",
  "file_count": 5,
  "total_size": 2039482048
}
10. Métadonnées des fichiers

Chaque fichier est annoncé avant son envoi.

{
  "type": "FILE_INFO",
  "name": "photo.jpg",
  "size": 20482048,
  "relative_path": "images/photo.jpg"
}
11. Transmission des données

Les données du fichier sont envoyées par blocs.

Exemple
BLOCK_SIZE = 4 MB

Chaque bloc est envoyé via la connexion TCP active.

12. Fin de transfert d'un fichier

Lorsque le fichier est entièrement transmis :

{
  "type": "FILE_COMPLETE"
}
13. Fin du transfert global

Lorsque tous les fichiers sont envoyés :

{
  "type": "TRANSFER_COMPLETE"
}
14. Gestion des erreurs

Si une erreur survient :

{
  "type": "TRANSFER_ERROR",
  "message": "disk write error"
}
15. Fermeture de session

Une fois le transfert terminé :

{
  "type": "SESSION_CLOSE"
}

La connexion TCP est ensuite fermée.

16. Diagramme simplifié de communication

Node A                    Node B

ANNOUNCE ---------> ANNOUNCE

TCP CONNECT -------->

SESSION_REQUEST ---->

                USER ACCEPT

<---- SESSION_ACCEPTED

AUTH_REQUEST ------>

<---- AUTH_RESPONSE

AUTH_SUCCESS <-----

TRANSFER_INIT ---->

FILE_INFO -------->

DATA BLOCKS ------>

FILE_COMPLETE ---->

TRANSFER_COMPLETE ->

SESSION_CLOSE ---->

16.1 Validation des messages

Chaque message reçu via TCP ou UDP doit être validé avant d’être traité.

La validation minimale doit vérifier :

le message est un JSON valide
le message contient un champ "type"
le type est reconnu par le protocole NodeDrop
les champs obligatoires du message sont présents

Si un message ne respecte pas ces règles :

le message est ignoré
un événement est enregistré dans les logs

Dans certains cas (erreur sur une session active), la session peut être fermée pour garantir la cohérence de la communication.

17. Évolutions futures du protocole

Les versions futures pourront ajouter :

chiffrement TLS

hash de vérification

reprise de transfert

compression

synchronisation de dossiers

communication distante

Le protocole V1 est volontairement simple afin de faciliter l’implémentation initiale.