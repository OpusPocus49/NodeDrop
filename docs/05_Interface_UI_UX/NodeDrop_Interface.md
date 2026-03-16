NodeDrop — Interface utilisateur (V1)
1. Objet du document

Ce document décrit l’interface utilisateur de NodeDrop pour la version 1.

Il définit :

les écrans principaux

les composants visuels

les interactions utilisateur

les informations affichées

le comportement de l’application

L’objectif est de créer une interface simple, claire et intuitive.

2. Principes de conception UX

L’interface NodeDrop doit respecter les principes suivants.

Simplicité

L’utilisateur doit pouvoir comprendre immédiatement comment envoyer un fichier.

Visibilité

Les informations importantes doivent être visibles :

machines disponibles

état des transferts

progression

erreurs éventuelles

Réactivité

L’interface ne doit jamais se bloquer pendant un transfert.

Confirmation des actions

Les actions importantes doivent être confirmées :

accepter un transfert

refuser un transfert

annuler un transfert

3. Structure générale de l’interface

NodeDrop comporte trois écrans principaux :

Fenêtre principale

Fenêtre de réception de transfert

Fenêtre de transfert en cours

4. Fenêtre principale

La fenêtre principale est l’écran central de NodeDrop.

Elle permet de :

voir les machines disponibles

se connecter à une machine

envoyer des fichiers

consulter les journaux

Structure de la fenêtre

L’interface peut être organisée en trois zones.

+---------------------------------------------------+
|                    NodeDrop                       |
+----------------------+----------------------------+
| Machines disponibles | Informations / actions     |
|                      |                            |
|  Alex-PC             |  Machine sélectionnée      |
|  Salon-PC            |                            |
|  Laptop-Marine       |  Boutons d’action          |
|                      |                            |
|                      |  - Connecter               |
|                      |  - Envoyer fichiers        |
|                      |                            |
+---------------------------------------------------+
|                Journal d'activité                 |
+---------------------------------------------------+
5. Liste des machines

La partie gauche affiche les machines détectées.

Informations affichées :

nom de la machine

adresse IP

statut

Statuts possibles
Statut	Description
Disponible	machine prête à accepter une connexion
Occupé	transfert en cours
Hors ligne	machine récemment détectée mais inactive
6. Sélection d'une machine

Lorsque l’utilisateur clique sur une machine :

Les informations suivantes apparaissent :

nom de la machine

adresse IP

statut

Boutons disponibles
Connecter

Permet d’envoyer une demande de connexion.

Envoyer fichiers

Permet de sélectionner des fichiers ou dossiers à envoyer.

Ce bouton n’est actif que si :

une session est ouverte

l’authentification est validée.

7. Sélection des fichiers

Lorsqu’un utilisateur clique sur Envoyer fichiers, une boîte de dialogue apparaît.

L’utilisateur peut sélectionner :

un fichier

plusieurs fichiers

un dossier complet

L’application affiche ensuite :

nombre de fichiers

taille totale

Avant de démarrer le transfert.

8. Fenêtre de réception

Lorsqu’un ordinateur souhaite envoyer des fichiers, la machine distante reçoit une notification.

Exemple :

+----------------------------------------+
|        Demande de transfert            |
+----------------------------------------+
| Machine source : Alex-PC               |
| Nombre de fichiers : 12                |
| Taille totale : 2.4 GB                 |
|                                        |
| Mot de passe : [___________]           |
|                                        |
| Destination : [Choisir dossier]        |
|                                        |
|     [ Accepter ]      [ Refuser ]      |
+----------------------------------------+
9. Fenêtre de transfert

Lorsque le transfert démarre, une fenêtre dédiée apparaît.

Elle affiche l’état du transfert.

Informations affichées

nom du fichier en cours

nombre de fichiers transférés

taille totale transférée

débit réseau

temps restant estimé

Exemple d’affichage
+-----------------------------------------+
|             Transfert en cours          |
+-----------------------------------------+
| Fichier : video.mp4                     |
| Progression :                           |
| [██████████------] 65%                  |
|                                         |
| Débit : 45 MB/s                         |
| Temps restant : 00:01:42                |
|                                         |
| Transféré : 1.3 GB / 2.0 GB             |
|                                         |
|              [ Annuler ]                |
+-----------------------------------------+
10. Gestion des erreurs

Si une erreur survient, l’utilisateur doit être informé.

Exemples :

Connexion refusée

Message :

Connexion refusée par la machine distante.
Mot de passe incorrect
Authentification échouée.
Erreur disque
Impossible d'écrire le fichier sur le disque.
11. Journal d’activité

La zone inférieure de la fenêtre principale affiche les événements récents.

Exemples :

[12:04] NodeDrop démarré
[12:04] Machine détectée : Alex-PC
[12:05] Connexion établie avec Salon-PC
[12:06] Transfert démarré
[12:07] Transfert terminé
12. Comportement de l’application
Au démarrage

NodeDrop :

démarre les services réseau

commence la découverte LAN

affiche les machines détectées

Pendant un transfert

l’interface reste réactive

la progression est mise à jour régulièrement

En cas de fermeture

Si un transfert est actif, l’application demande confirmation avant de quitter.

13. Évolutions futures de l’interface

Dans les versions futures, l’interface pourra intégrer :

mode sombre

historique des transferts

synchronisation de dossiers

gestion d’organisations

connexion distante

statistiques réseau