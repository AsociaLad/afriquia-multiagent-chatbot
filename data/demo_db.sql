-- ============================================================
-- Afriquia / AlloGaz — Base de démo MVP
-- Script réexécutable : DROP → CREATE → INSERT → READ-ONLY USER
-- ============================================================

-- ============================================================
-- 1. NETTOYAGE (ordre inverse des dépendances FK)
-- ============================================================

DROP TABLE IF EXISTS reclamations CASCADE;
DROP TABLE IF EXISTS livraisons   CASCADE;
DROP TABLE IF EXISTS commandes    CASCADE;
DROP TABLE IF EXISTS clients      CASCADE;
DROP TABLE IF EXISTS produits     CASCADE;

-- ============================================================
-- 2. CRÉATION DES TABLES
-- ============================================================

CREATE TABLE produits (
    id              SERIAL PRIMARY KEY,
    nom             VARCHAR(100) NOT NULL,
    categorie       VARCHAR(50)  NOT NULL,   -- 'carburant' | 'gaz'
    prix_unitaire   DECIMAL(10,2) NOT NULL,
    unite           VARCHAR(20)  NOT NULL,   -- 'L' | 'bouteille'
    date_maj        DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE clients (
    id              SERIAL PRIMARY KEY,
    nom             VARCHAR(100) NOT NULL,
    ville           VARCHAR(50)  NOT NULL,
    type_client     VARCHAR(20)  NOT NULL,   -- 'particulier' | 'entreprise'
    telephone       VARCHAR(20)
);

CREATE TABLE commandes (
    id              SERIAL PRIMARY KEY,
    client_id       INT NOT NULL REFERENCES clients(id),
    produit_id      INT NOT NULL REFERENCES produits(id),
    quantite        DECIMAL(10,2) NOT NULL,
    montant_total   DECIMAL(12,2) NOT NULL,
    statut          VARCHAR(30) NOT NULL,    -- 'en_attente' | 'confirmee' | 'en_livraison' | 'livree' | 'annulee'
    date_commande   TIMESTAMP NOT NULL DEFAULT NOW(),
    date_livraison  TIMESTAMP
);

CREATE TABLE livraisons (
    id              SERIAL PRIMARY KEY,
    commande_id     INT NOT NULL REFERENCES commandes(id),
    livreur         VARCHAR(100) NOT NULL,
    statut          VARCHAR(30) NOT NULL,    -- 'en_cours' | 'livree' | 'echouee'
    date_depart     TIMESTAMP NOT NULL,
    date_arrivee    TIMESTAMP
);

CREATE TABLE reclamations (
    id              SERIAL PRIMARY KEY,
    client_id       INT NOT NULL REFERENCES clients(id),
    commande_id     INT NOT NULL REFERENCES commandes(id),
    sujet           VARCHAR(200) NOT NULL,
    statut          VARCHAR(30) NOT NULL,    -- 'ouverte' | 'en_cours' | 'resolue'
    date_creation   TIMESTAMP NOT NULL DEFAULT NOW()
);

-- ============================================================
-- 3. DONNÉES DE DÉMO
-- ============================================================

-- --- Produits (6 lignes) ---

INSERT INTO produits (nom, categorie, prix_unitaire, unite, date_maj) VALUES
('Gazoil 50 ppm',       'carburant', 12.45, 'L',         '2025-03-28'),
('Essence SP95',        'carburant', 14.89, 'L',         '2025-03-28'),
('GPL Carburant',       'carburant',  7.20, 'L',         '2025-03-28'),
('Butane 6 kg',         'gaz',       40.00, 'bouteille', '2025-03-15'),
('Butane 12 kg',        'gaz',       80.00, 'bouteille', '2025-03-15'),
('Propane 35 kg',       'gaz',      350.00, 'bouteille', '2025-03-15');

-- --- Clients (8 lignes) ---

INSERT INTO clients (nom, ville, type_client, telephone) VALUES
('Youssef El Amrani',     'Casablanca',  'particulier', '0661-123456'),
('Fatima Zahra Bennis',   'Rabat',       'particulier', '0662-234567'),
('Ahmed Tazi',            'Tanger',      'particulier', '0663-345678'),
('Nadia Oukacha',         'Marrakech',   'particulier', '0664-456789'),
('Transport Atlas SARL',  'Casablanca',  'entreprise',  '0522-112233'),
('Hôtel Palmeraie SA',    'Marrakech',   'entreprise',  '0524-445566'),
('Coopérative Al Baraka', 'Fès',         'entreprise',  '0535-667788'),
('Logistique Nord SARL',  'Tanger',      'entreprise',  '0539-889900');

-- --- Commandes (18 lignes) ---
-- Statuts variés, dates réparties sur mars 2025

INSERT INTO commandes (client_id, produit_id, quantite, montant_total, statut, date_commande, date_livraison) VALUES
-- Livrées
(1, 1, 100.00,  1245.00, 'livree',       '2025-03-01 09:00', '2025-03-03 14:00'),
(2, 4,   5.00,   200.00, 'livree',       '2025-03-02 10:30', '2025-03-03 11:00'),
(5, 1, 5000.00, 62250.00,'livree',       '2025-03-04 08:00', '2025-03-06 16:00'),
(3, 2,  50.00,   744.50, 'livree',       '2025-03-07 11:00', '2025-03-09 10:00'),
(6, 6,  10.00,  3500.00, 'livree',       '2025-03-08 09:30', '2025-03-10 15:00'),
(4, 5,   3.00,   240.00, 'livree',       '2025-03-10 14:00', '2025-03-12 09:00'),
(7, 1, 2000.00, 24900.00,'livree',       '2025-03-11 07:30', '2025-03-13 17:00'),
-- En livraison
(1, 5,   2.00,   160.00, 'en_livraison', '2025-03-25 08:00', NULL),
(8, 1, 3000.00, 37350.00,'en_livraison', '2025-03-25 09:00', NULL),
(2, 4,   4.00,   160.00, 'en_livraison', '2025-03-26 10:00', NULL),
(5, 3, 1000.00,  7200.00,'en_livraison', '2025-03-26 11:00', NULL),
-- Confirmées
(3, 1,  200.00,  2490.00, 'confirmee',   '2025-03-27 09:00', NULL),
(4, 2,   80.00,  1191.20, 'confirmee',   '2025-03-28 10:00', NULL),
(6, 5,   5.00,   400.00,  'confirmee',   '2025-03-28 14:00', NULL),
-- En attente
(7, 6,   3.00,  1050.00, 'en_attente',   '2025-03-29 08:00', NULL),
(1, 2,   40.00,  595.60, 'en_attente',   '2025-03-30 09:00', NULL),
-- Annulée
(8, 4,  10.00,   400.00, 'annulee',      '2025-03-20 11:00', NULL),
-- Commande récente
(2, 1,  150.00, 1867.50, 'confirmee',    '2025-03-30 15:00', NULL);

-- --- Livraisons (10 lignes) ---

INSERT INTO livraisons (commande_id, livreur, statut, date_depart, date_arrivee) VALUES
-- Livrées (correspondent aux commandes livrées)
(1,  'Karim Bouazza',   'livree',   '2025-03-02 08:00', '2025-03-03 14:00'),
(2,  'Hassan Filali',   'livree',   '2025-03-03 07:00', '2025-03-03 11:00'),
(3,  'Karim Bouazza',   'livree',   '2025-03-05 06:00', '2025-03-06 16:00'),
(4,  'Omar Senhaji',    'livree',   '2025-03-08 08:00', '2025-03-09 10:00'),
(5,  'Hassan Filali',   'livree',   '2025-03-09 07:00', '2025-03-10 15:00'),
(6,  'Omar Senhaji',    'livree',   '2025-03-11 08:00', '2025-03-12 09:00'),
(7,  'Karim Bouazza',   'livree',   '2025-03-12 06:00', '2025-03-13 17:00'),
-- En cours (correspondent aux commandes en_livraison)
(8,  'Hassan Filali',   'en_cours', '2025-03-26 07:00', NULL),
(9,  'Karim Bouazza',   'en_cours', '2025-03-26 08:00', NULL),
(10, 'Omar Senhaji',    'en_cours', '2025-03-27 07:00', NULL);

-- --- Réclamations (5 lignes) ---

INSERT INTO reclamations (client_id, commande_id, sujet, statut, date_creation) VALUES
(1, 1,  'Retard de livraison de 2 heures',                       'resolue',  '2025-03-03 16:00'),
(3, 4,  'Quantité livrée inférieure à la commande (48L au lieu de 50L)', 'resolue',  '2025-03-09 12:00'),
(8, 17, 'Commande annulée mais pas de remboursement reçu',       'ouverte',  '2025-03-22 10:00'),
(5, 3,  'Facture non conforme au montant convenu',                'en_cours', '2025-03-07 09:00'),
(2, 10, 'Bouteille de gaz reçue endommagée',                     'ouverte',  '2025-03-27 11:00');

-- ============================================================
-- 4. UTILISATEUR READ-ONLY POUR LE SQL AGENT
-- ============================================================

DO $$
BEGIN
    -- Créer l'utilisateur s'il n'existe pas
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'sql_agent_reader') THEN
        CREATE ROLE sql_agent_reader WITH LOGIN PASSWORD 'reader_afriquia_2025';
    END IF;
END
$$;

-- Droits d'accès
GRANT CONNECT ON DATABASE chatbot_db TO sql_agent_reader;
GRANT USAGE ON SCHEMA public TO sql_agent_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO sql_agent_reader;

-- Appliquer aussi aux futures tables créées dans ce schéma
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO sql_agent_reader;

-- ============================================================
-- 5. REQUÊTES DE VÉRIFICATION
-- ============================================================

-- Q1 : Prix du gazoil
-- SELECT nom, prix_unitaire, unite FROM produits WHERE nom ILIKE '%gazoil%';
-- → Gazoil 50 ppm | 12.45 | L

-- Q2 : Commandes en livraison avec nom du client et produit
-- SELECT c.id, cl.nom AS client, p.nom AS produit, c.quantite, c.statut
-- FROM commandes c
-- JOIN clients cl ON cl.id = c.client_id
-- JOIN produits p ON p.id = c.produit_id
-- WHERE c.statut = 'en_livraison';
-- → 4 lignes

-- Q3 : Réclamations ouvertes avec détail client
-- SELECT r.id, cl.nom AS client, r.sujet, r.statut
-- FROM reclamations r
-- JOIN clients cl ON cl.id = r.client_id
-- WHERE r.statut = 'ouverte';
-- → 2 lignes

-- Q4 : Total dépensé par client (top 5)
-- SELECT cl.nom, SUM(c.montant_total) AS total_depense
-- FROM commandes c
-- JOIN clients cl ON cl.id = c.client_id
-- WHERE c.statut != 'annulee'
-- GROUP BY cl.nom
-- ORDER BY total_depense DESC
-- LIMIT 5;

-- Q5 : Nombre de commandes par statut
-- SELECT statut, COUNT(*) AS nb FROM commandes GROUP BY statut ORDER BY nb DESC;
-- → livree: 7, en_livraison: 4, confirmee: 4, en_attente: 2, annulee: 1
