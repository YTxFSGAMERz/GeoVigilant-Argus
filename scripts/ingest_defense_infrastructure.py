"""
ARGUS DATASET — Critical Defense & Strategic Infrastructure Ingestion Engine.

Ingests strategic defense installations, nuclear facilities, orbital launch spaceports,
and international law enforcement headquarters into state_tracker.db.
"""

import os
import sys
import sqlite3
import time

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "ARGUS_DATASET", "indexes", "state_tracker.db")

# 1. Global Military Installations
MILITARY_BASES = [
    ("Ream Naval Base", "military_base", "CHINA", 10.5034, 103.6090, "KHM", "PLA naval facility with deep-water docking.", "ELEVATED"),
    ("Chinese PLA Support Base", "military_base", "CHINA", 11.5915, 43.0602, "DJI", "First overseas Chinese military outpost on Bab-el-Mandeb.", "ELEVATED"),
    ("N'Djamena Air Force Base", "military_base", "FRANCE", 12.1336, 15.0339, "TCD", "French Air and Space Force Sahel operations hub.", "ELEVATED"),
    ("Naval Base of Héron", "military_base", "FRANCE", 11.5566, 43.1442, "DJI", "French naval forces base at Djibouti port.", "GUARDED"),
    ("Port of Shahid Beheshti", "military_base", "INDIA", 25.2975, 60.6111, "IRN", "Chabahar port terminal developed with strategic naval access.", "GUARDED"),
    ("Russian 102nd Military Base", "military_base", "RUSSIA", 40.7900, 43.8250, "ARM", "Major Russian Transcaucasian forward command garrison.", "HIGH"),
    ("Khmeimim Air Base", "military_base", "RUSSIA", 35.4110, 35.9450, "SYR", "Russian Aerospace Forces primary Syrian combat operating airfield.", "CRITICAL"),
    ("HMS Jufair (NSA Bahrain)", "military_base", "UK", 26.2050, 50.6150, "BHR", "Royal Navy Persian Gulf forward naval support facility.", "HIGH"),
    ("RAF Akrotiri", "military_base", "UK", 34.5900, 32.9870, "CYP", "Sovereign Base Area airfield supporting Eastern Mediterranean missions.", "HIGH"),
    ("Andersen Air Force Base", "military_base", "US-NATO", 13.5792, 144.9230, "GUM", "USAF Pacific Command forward nuclear-capable bomber hub.", "HIGH"),
    ("Naval Support Activity Bahrain", "military_base", "US-NATO", 26.2086, 50.6097, "BHR", "US Fifth Fleet command headquarters covering Arabian Gulf.", "CRITICAL"),
    ("Ramstein Air Base", "military_base", "US-NATO", 49.4430, 7.7716, "DEU", "Headquarters of US Air Forces in Europe and NATO Allied Air Command.", "HIGH"),
    ("Kadena Air Base", "military_base", "US-NATO", 26.3556, 127.7675, "JPN", "Hub of airpower in the Pacific with multiple fighter wings.", "HIGH"),
    ("Yokota Air Base", "military_base", "US-NATO", 35.7394, 139.3470, "JPN", "US Forces Japan and 5th Air Force headquarters.", "GUARDED"),
    ("USAG Camp Humphreys", "military_base", "US-NATO", 36.9651, 127.0330, "KOR", "Largest overseas US military installation; United Nations Command HQ.", "HIGH"),
    ("Naval Station Norfolk", "military_base", "US-NATO", 36.9500, -76.3100, "USA", "World's largest naval base and US Fleet Forces Command headquarters.", "GUARDED"),
    ("Camp Pendleton", "military_base", "US-NATO", 33.3800, -117.4000, "USA", "Major US Marine Corps West Coast expeditionary training base.", "GUARDED"),
    ("Naval Base San Diego", "military_base", "US-NATO", 32.6800, -117.1300, "USA", "Primary Pacific Fleet surface combatant homeport.", "GUARDED"),
    ("Nellis Air Force Base", "military_base", "US-NATO", 36.2400, -115.0300, "USA", "USAF Warfare Center, Red Flag exercises and test range.", "GUARDED"),
    ("Langley Air Force Base", "military_base", "US-NATO", 37.0800, -76.3600, "USA", "Air Combat Command HQ and premier F-22 Raptor base.", "GUARDED"),
    ("Cheyenne Mountain Complex", "military_base", "US-NATO", 38.7400, -104.8500, "USA", "Bunker NORAD alternate command center hardened against EMP.", "HIGH"),
    ("Naval Submarine Base Kings Bay", "military_base", "US-NATO", 30.8000, -81.5200, "USA", "Atlantic homeport for Ohio-class nuclear ballistic missile submarines.", "HIGH"),
    ("Naval Base Kitsap", "military_base", "US-NATO", 47.5600, -122.6600, "USA", "Pacific Trident nuclear ballistic submarine homeport and shipyard.", "HIGH"),
    ("Yokosuka Naval Base", "military_base", "US-NATO", 35.2800, 139.6700, "JPN", "US Seventh Fleet forward-deployed aircraft carrier homeport.", "HIGH"),
    ("Naval Station Rota", "military_base", "US-NATO", 36.6200, -6.3500, "ESP", "Aegis Ballistic Missile Defense destroyers European base.", "HIGH"),
    ("Incirlik Air Base", "military_base", "US-NATO", 37.0000, 35.4300, "TUR", "Strategic NATO nuclear weapons sharing airfield near Middle East.", "HIGH"),
    ("Kaliningrad Chkalovsk Naval Air", "military_base", "RUSSIA", 54.7100, 20.5100, "RUS", "Russian Baltic Fleet bastion with Iskander missile batteries.", "CRITICAL"),
    ("Sevastopol Naval Base", "military_base", "RUSSIA", 44.6000, 33.5000, "UKR", "Contested Black Sea Fleet major deep-water warm port.", "CRITICAL"),
    ("Vladivostok Naval Base", "military_base", "RUSSIA", 43.1200, 131.9000, "RUS", "Russian Pacific Fleet headquarters.", "HIGH"),
    ("Severomorsk / Murmansk Base", "military_base", "RUSSIA", 68.9700, 33.0900, "RUS", "Russian Northern Fleet nuclear submarine bastion.", "CRITICAL"),
    ("Diego Garcia Naval Support Facility", "military_base", "US-NATO", -7.3200, 72.4200, "IOT", "Strategic Indian Ocean bomber base and nuclear submarine tender.", "HIGH"),
    ("Al Udeid Air Base", "military_base", "US-NATO", 25.1200, 51.3100, "QAT", "US Combined Air Operations Center for US Central Command.", "HIGH"),
    ("Al Dhafra Air Base", "military_base", "US-NATO", 24.2500, 54.5500, "ARE", "Key forward base for US stealth fighters and surveillance drones.", "HIGH"),
    ("Camp Lemonnier", "military_base", "US-NATO", 11.5500, 43.1400, "DJI", "Only permanent US military base in Africa, supporting AFRICOM.", "HIGH"),
    ("Misawa Air Base", "military_base", "US-NATO", 40.7000, 141.3700, "JPN", "Bilateral air combat intelligence and electronic warfare base.", "GUARDED"),
    ("Osan Air Base", "military_base", "US-NATO", 37.0900, 127.0300, "KOR", "Seventh Air Force forward air defense airfield.", "HIGH"),
    ("Spangdahlem Air Base", "military_base", "US-NATO", 49.9700, 6.6900, "DEU", "USAF 52nd Fighter Wing European SEAD strike airfield.", "GUARDED"),
    ("Aviano Air Base", "military_base", "US-NATO", 46.0300, 12.6000, "ITA", "NATO southern flank airbase hosting B61 nuclear assets.", "HIGH"),
    ("NAS Sigonella", "military_base", "US-NATO", 37.4000, 14.9200, "ITA", "Crossroads of the Mediterranean; maritime patrol and drone hub.", "HIGH"),
    ("Thule Air Base (Pituffik)", "military_base", "US-NATO", 76.5300, -68.7400, "GRL", "US Space Force northernmost early-warning radar site.", "HIGH"),
    ("Pearl Harbor-Hickam Joint Base", "military_base", "US-NATO", 21.3500, -157.9700, "USA", "Headquarters of US Indo-Pacific Command.", "HIGH"),
    ("The Pentagon", "military_base", "US-NATO", 38.8700, -77.0600, "USA", "Headquarters of the United States Department of Defense.", "HIGH"),
    ("Area 51 (Groom Lake)", "military_base", "US-NATO", 37.2400, -115.8200, "USA", "Highly classified USAF experimental flight test facility.", "CRITICAL"),
    ("Sanya (Yulin) Naval Base", "military_base", "CHINA", 18.2200, 109.4900, "CHN", "Subterranean submarine caverns for Type 094 nuclear subs.", "CRITICAL"),
    ("Fiery Cross Reef", "military_base", "CHINA", 9.5500, 112.8900, "CHN", "Militarized artificial island with 3,000m runway in South China Sea.", "CRITICAL"),
    ("Subi Reef Strategic Outpost", "military_base", "CHINA", 10.9300, 114.0800, "CHN", "Sensors, anti-aircraft missiles, and radar dome installations.", "CRITICAL"),
    ("Mischief Reef Fortress", "military_base", "CHINA", 9.9000, 115.5300, "CHN", "Fortified naval port and missile shelters inside lagoon.", "CRITICAL"),
    ("Tartus Naval Base", "military_base", "RUSSIA", 34.9000, 35.8600, "SYR", "Only Russian Mediterranean repair and replenishment station.", "CRITICAL"),
    ("INS Karwar (Project Seabird)", "military_base", "INDIA", 14.8200, 74.1200, "IND", "Major Indian Navy deep-water base for aircraft carriers and subs.", "GUARDED"),
    ("Sinpo South Shipyard", "military_base", "NORTH-KOREA", 40.0100, 128.1800, "PRK", "North Korean ballistic missile submarine development center.", "CRITICAL")
]

# 2. Global Nuclear Power & Enrichment Sites
NUCLEAR_SITES = [
    ("Chernobyl Nuclear Power Plant", "nuclear_facility", "IAEA", 51.3892, 30.0997, "UKR", "Site of the 1986 disaster; active confinement shelter monitoring.", "HIGH"),
    ("Fukushima Daiichi", "nuclear_facility", "IAEA", 37.4214, 141.0325, "JPN", "Decommissioning complex following 2011 triple meltdown.", "HIGH"),
    ("Zaporizhzhia Nuclear Plant", "nuclear_facility", "IAEA", 47.5110, 34.5850, "UKR", "Largest nuclear power plant in Europe, heavily contested combat zone.", "CRITICAL"),
    ("Natanz Uranium Enrichment Facility", "nuclear_facility", "IRN", 33.7240, 51.7280, "IRN", "Primary Iranian gas centrifuge uranium enrichment underground complex.", "CRITICAL"),
    ("Fordow Fuel Enrichment Plant", "nuclear_facility", "IRN", 34.8840, 50.9960, "IRN", "Deep mountain underground enrichment facility hardened against bunker busters.", "CRITICAL"),
    ("Dimona (Negev Nuclear Center)", "nuclear_facility", "ISR", 31.0010, 35.1450, "ISR", "Undeclared nuclear reactor and plutonium extraction facility.", "CRITICAL"),
    ("Yongbyon Nuclear Scientific Center", "nuclear_facility", "PRK", 39.7990, 125.7550, "PRK", "North Korea main plutonium and highly-enriched uranium complex.", "CRITICAL"),
    ("Kahuta Research Laboratories", "nuclear_facility", "PAK", 33.5900, 73.4000, "PAK", "Pakistan primary gas centrifuge enrichment and weapons design site.", "CRITICAL"),
    ("Sellafield Nuclear Complex", "nuclear_facility", "UK", 54.4200, -3.4980, "GBR", "Major nuclear reprocessing and decommissioning site.", "GUARDED"),
    ("La Hague Reprocessing Facility", "nuclear_facility", "FRANCE", 49.6780, -1.8820, "FRA", "World largest light water reactor spent fuel reprocessing plant.", "GUARDED"),
    ("Palo Verde Generating Station", "nuclear_facility", "USA", 33.3900, -112.8600, "USA", "Largest nuclear power generation facility in the United States.", "GUARDED"),
    ("Bushehr Nuclear Power Plant", "nuclear_facility", "IAEA", 28.8300, 50.8870, "IRN", "First commercial civilian nuclear power plant in the Middle East.", "HIGH"),
    ("Barakah Nuclear Energy Plant", "nuclear_facility", "ARE", 23.9670, 52.2600, "ARE", "First commercial nuclear plant on Arabian Peninsula (4 APR-1400 units).", "GUARDED"),
    ("Kudankulam Nuclear Power Plant", "nuclear_facility", "INDIA", 8.1690, 77.7120, "IND", "Highest capacity nuclear plant in India, equipped with VVER-1000 reactors.", "GUARDED")
]

# 3. Global Orbital Spaceports
SPACEPORTS = [
    ("Kennedy Space Center / Cape Canaveral", "spaceport", "US-NASA", 28.5729, -80.6490, "USA", "Primary American space launch complex and human spaceflight base.", "GUARDED"),
    ("Baikonur Cosmodrome", "spaceport", "RUSSIA-KAZ", 45.9650, 63.3050, "KAZ", "World first and largest operational space launch facility.", "GUARDED"),
    ("Guiana Space Centre (Kourou)", "spaceport", "ESA", 5.2372, -52.7606, "GUF", "European Space Agency equatorial spaceport for Ariane launchers.", "GUARDED"),
    ("Tanegashima Space Center", "spaceport", "JAXA", 30.3997, 130.9680, "JPN", "Japan main spaceport on Tanegashima island for H3 rockets.", "GUARDED"),
    ("Jiuquan Satellite Launch Center", "spaceport", "CNSA", 40.9606, 100.2980, "CHN", "China first spaceport; primary site for crewed Shenzhou missions.", "HIGH"),
    ("Wenchang Space Launch Site", "spaceport", "CNSA", 19.6144, 110.9510, "CHN", "Coastal spaceport launching Long March 5 heavy-lift rockets.", "HIGH"),
    ("Satish Dhawan Space Centre (Sriharikota)", "spaceport", "ISRO", 13.7200, 80.2300, "IND", "Indian Space Research Organisation orbital launch complex.", "GUARDED"),
    ("Vandenberg Space Force Base", "spaceport", "USSF", 34.7328, -120.5680, "USA", "West coast spaceport for polar orbital military and commercial launches.", "GUARDED"),
    ("Vostochny Cosmodrome", "spaceport", "RUSSIA", 51.8844, 128.3340, "RUS", "Modern Russian civil spaceport in Amur Oblast for Angara rockets.", "GUARDED")
]

# 4. International Law Enforcement & Intelligence Headquarters
LAW_ENFORCEMENT_HQ = [
    ("INTERPOL General Secretariat", "law_enforcement_hq", "INTERPOL", 45.7820, 4.8560, "FRA", "Global headquarters of the International Criminal Police Organization.", "HIGH"),
    ("Europol Headquarters", "law_enforcement_hq", "EUROPOL", 52.0880, 4.2810, "NLD", "European Union Agency for Law Enforcement Cooperation, The Hague.", "HIGH"),
    ("FBI Headquarters (J. Edgar Hoover)", "law_enforcement_hq", "USA-DOJ", 38.8950, -77.0240, "USA", "Headquarters of the Federal Bureau of Investigation, Washington D.C.", "HIGH"),
    ("New Scotland Yard", "law_enforcement_hq", "UK-POLICE", 51.4980, -0.1330, "GBR", "Headquarters of the Metropolitan Police Service, London.", "GUARDED"),
    ("BKA Headquarters Wiesbaden", "law_enforcement_hq", "GERMANY", 50.0820, 8.2400, "DEU", "Federal Criminal Police Office of Germany.", "GUARDED"),
    ("DGSI Headquarters", "law_enforcement_hq", "FRANCE", 48.9050, 2.2850, "FRA", "General Directorate for Internal Security, Levallois-Perret.", "HIGH"),
    ("MI5 Thames House", "law_enforcement_hq", "UK", 51.4940, -0.1260, "GBR", "Headquarters of the British Security Service.", "CRITICAL"),
    ("MI6 SIS Headquarters", "law_enforcement_hq", "UK", 51.4870, -0.1240, "GBR", "Secret Intelligence Service building, Vauxhall Cross London.", "CRITICAL"),
    ("BND Headquarters Berlin", "law_enforcement_hq", "GERMANY", 52.5340, 13.3770, "DEU", "Federal Intelligence Service of Germany headquarters.", "HIGH"),
    ("Mossad Headquarters", "law_enforcement_hq", "ISRAEL", 32.1460, 34.8380, "ISR", "National intelligence agency of Israel.", "CRITICAL")
]


def ingest_all_defense():
    print("================================================================")
    print("   ARGUS DATASET — CRITICAL DEFENSE & SECURITY INFRASTRUCTURE  ")
    print("================================================================")
    t0 = time.time()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS critical_defense_infrastructure (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            facility_name TEXT NOT NULL,
            facility_type TEXT NOT NULL,
            affiliation TEXT,
            latitude REAL NOT NULL,
            longitude REAL NOT NULL,
            country TEXT,
            description TEXT,
            threat_level TEXT DEFAULT 'GUARDED',
            status TEXT DEFAULT 'ACTIVE'
        )
    """)

    c.execute("CREATE INDEX IF NOT EXISTS idx_defense_coords ON critical_defense_infrastructure(latitude, longitude)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_defense_type ON critical_defense_infrastructure(facility_type)")

    c.execute("DELETE FROM critical_defense_infrastructure")

    all_records = []
    for item in MILITARY_BASES + NUCLEAR_SITES + SPACEPORTS + LAW_ENFORCEMENT_HQ:
        name, ftype, affil, lat, lon, country, desc, threat = item
        all_records.append((name, ftype, affil, float(lat), float(lon), country, desc, threat, "ACTIVE"))

    c.executemany("""
        INSERT INTO critical_defense_infrastructure (
            facility_name, facility_type, affiliation, latitude, longitude,
            country, description, threat_level, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, all_records)

    conn.commit()

    c.execute("SELECT facility_type, COUNT(*) FROM critical_defense_infrastructure GROUP BY facility_type")
    breakdown = c.fetchall()

    print(f"✓ Successfully ingested {len(all_records)} strategic defense facilities in {time.time() - t0:.2f}s:")
    for ftype, count in breakdown:
        print(f"  • {ftype.replace('_', ' ').title()}: {count} facilities")

    conn.close()
    print("================================================================")


if __name__ == "__main__":
    ingest_all_defense()
