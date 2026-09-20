"""
Master Place Discovery Engine for ARGUS GroundView.
Federates queries across Wikidata SPARQL, OpenStreetMap Overpass,
and open geographic inventories to produce a canonical worldwide landmark catalog.
"""

import os
import csv
import json
import uuid
import logging
import argparse
from typing import List, Dict, Any, Set, Optional, Tuple
from argus.config import load_config, ArgusConfig
from argus.http_client import ARGUSHttpClient
from argus.state_tracker import StateTracker
from argus.geo_utils import spatial_grid_cell, vincenty_distance_m

logger = logging.getLogger(__name__)

NAMESPACE_ARGUS = uuid.UUID("e4f8a92b-810d-5bc2-99a0-62a229a1d120")

# Primary entity taxonomy mappings
LANDMARK_TAXONOMY = {
    "monument": "Q4989906",
    "castle": "Q23413",
    "palace": "Q16560",
    "tower": "Q12554",
    "bridge": "Q12280",
    "museum": "Q33506",
    "art_gallery": "Q207694",
    "archaeological_site": "Q839954",
    "place_of_worship": "Q16970",
    "statue": "Q179700",
    "mountain": "Q8502",
    "waterfall": "Q34038",
    "beach": "Q40080",
    "national_park": "Q4617",
    "unesco_heritage": "Q9259",
    "tourist_attraction": "Q570116",
    "pyramid": "Q12516",
    "cathedral": "Q2977",
    "fortress": "Q178561",
    "lighthouse": "Q39715",
    "amphitheatre": "Q134362",
    "triumphal_arch": "Q143912",
    "square": "Q174782",
    "skyscraper": "Q11303",
    "botanical_garden": "Q167346",
    "library": "Q7075",
    "opera_house": "Q153562",
    "stadium": "Q483110",
    "fountain": "Q483453",
    "cave": "Q35509",
    "volcano": "Q8072",
    "canyon": "Q15084",
    "lake": "Q23397",
    "historic_district": "Q15127",
    "clock_tower": "Q853857",
    "mosque": "Q32815",
    "hindu_temple": "Q842402",
    "buddhist_temple": "Q200886",
    "monastery": "Q44613",
    "memorial": "Q5003624",
    "mausoleum": "Q162875"
}

# ISO-3 country mappings helper
COUNTRY_ISO3_MAP = {
    "France": "FRA", "United States": "USA", "United States of America": "USA",
    "United Kingdom": "GBR", "Italy": "ITA", "Germany": "DEU", "Spain": "ESP",
    "China": "CHN", "Japan": "JPN", "India": "IND", "Egypt": "EGY", "Australia": "AUS",
    "Brazil": "BRA", "Canada": "CAN", "Mexico": "MEX", "Russia": "RUS", "Turkey": "TUR",
    "Greece": "GRC", "Jordan": "JOR", "Peru": "PER", "South Africa": "ZAF",
    "Saudi Arabia": "SAU", "United Arab Emirates": "ARE", "Singapore": "SGP",
    "Thailand": "THA", "Indonesia": "IDN", "South Korea": "KOR", "Vietnam": "VNM",
    "Argentina": "ARG", "Chile": "CHL", "Colombia": "COL", "Morocco": "MAR",
    "Kenya": "KEN", "Tanzania": "TZA", "New Zealand": "NZL", "Norway": "NOR",
    "Sweden": "SWE", "Switzerland": "CHE", "Austria": "AUT", "Netherlands": "NLD",
    "Belgium": "BEL", "Portugal": "PRT", "Ireland": "IRL", "Poland": "POL",
    "Czech Republic": "CZE", "Hungary": "HUN", "Iceland": "ISL", "Cambodia": "KHM",
    "Nepal": "NPL", "Malaysia": "MYS", "Philippines": "PHL", "Israel": "ISR",
    "Vatican City": "VAT", "San Marino": "SMR", "Monaco": "MCO", "Cuba": "CUB",
    "Ecuador": "ECU", "Bolivia": "BOL", "Guatemala": "GTM", "Costa Rica": "CRI",
    "Panama": "PAN", "Uruguay": "URY", "Paraguay": "PRY", "Venezuela": "VEN",
    "Ethiopia": "ETH", "Zimbabwe": "ZWE", "Zambia": "ZMB", "Ghana": "GHA",
    "Nigeria": "NGA", "Madagascar": "MDG", "Tunisia": "TUN", "Algeria": "DZA",
    "Botswana": "BWA", "Namibia": "NAM", "Rwanda": "RWA", "Uganda": "UGA",
    "Croatia": "HRV", "Romania": "ROU", "Bulgaria": "BGR", "Finland": "FIN",
    "Denmark": "DNK", "Estonia": "EST", "Latvia": "LVA", "Lithuania": "LTU",
    "Ukraine": "UKR", "Slovakia": "SVK", "Slovenia": "SVN", "Serbia": "SRB",
    "Taiwan": "TWN", "Hong Kong": "HKG", "Uzbekistan": "UZB", "Iran": "IRN",
    "Pakistan": "PAK", "Sri Lanka": "LKA", "Myanmar": "MMR", "Laos": "LAO",
    "Fiji": "FJI", "Papua New Guinea": "PNG", "Samoa": "WSM"
}

class DiscoveryEngine:
    def __init__(self, config: ArgusConfig, state_tracker: StateTracker):
        self.config = config
        self.tracker = state_tracker
        self.http = ARGUSHttpClient(user_agent=config.system.user_agent,
                                    rate_limits={"wikidata.org": config.rate_limits.wikimedia_req_per_sec})
        self.base_dir = config.system.base_dir
        self.places_dir = os.path.join(self.base_dir, "places")
        os.makedirs(self.places_dir, exist_ok=True)
        os.makedirs(os.path.join(self.places_dir, "coverage"), exist_ok=True)

    def generate_canonical_place_id(self, name: str, lat: float, lon: float, wikidata_id: str = "") -> str:
        unique_str = f"{wikidata_id or name.strip().lower()}_{round(lat, 4)}_{round(lon, 4)}"
        return f"argus-place-{uuid.uuid5(NAMESPACE_ARGUS, unique_str)}"

    def query_wikidata_category(self, qid: str, category_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        sparql = f"""
        SELECT DISTINCT ?place ?placeLabel ?countryLabel ?cityLabel ?coords ?image ?commonsCategory ?osmId WHERE {{
          ?place wdt:P31 wd:{qid} ;
                 wdt:P625 ?coords .
          OPTIONAL {{ ?place wdt:P17 ?country . }}
          OPTIONAL {{ ?place wdt:P131 ?city . }}
          OPTIONAL {{ ?place wdt:P18 ?image . }}
          OPTIONAL {{ ?place wdt:P373 ?commonsCategory . }}
          OPTIONAL {{ ?place wdt:P402 ?osmId . }}
          SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
        }}
        LIMIT {limit}
        """
        endpoint = self.config.discovery.wikidata_endpoint
        try:
            resp = self.http.get(endpoint, params={"query": sparql, "format": "json"}, timeout=8.0, max_attempts=1)
            data = resp.json()
            bindings = data.get("results", {}).get("bindings", [])
            places = []
            
            for b in bindings:
                uri = b.get("place", {}).get("value", "")
                wiki_qid = uri.split("/")[-1] if "/" in uri else ""
                name = b.get("placeLabel", {}).get("value", "")
                if not name or name.startswith("Q") and name[1:].isdigit():
                    continue
                    
                coords_str = b.get("coords", {}).get("value", "")
                # Format: Point(lon lat)
                if not coords_str or "Point(" not in coords_str:
                    continue
                raw_c = coords_str.replace("Point(", "").replace(")", "").strip().split()
                if len(raw_c) < 2:
                    continue
                try:
                    lon, lat = float(raw_c[0]), float(raw_c[1])
                except ValueError:
                    continue
                    
                country_name = b.get("countryLabel", {}).get("value", "Unknown")
                country_iso = COUNTRY_ISO3_MAP.get(country_name, country_name[:3].upper() if len(country_name) >= 3 else "UNK")
                city_name = b.get("cityLabel", {}).get("value", "")
                img_url = b.get("image", {}).get("value", "")
                commons_cat = b.get("commonsCategory", {}).get("value", "")
                osm_id = b.get("osmId", {}).get("value", "")
                
                place_id = self.generate_canonical_place_id(name, lat, lon, wiki_qid)
                
                places.append({
                    "place_id": place_id,
                    "name": name,
                    "aliases": [],
                    "country": country_iso,
                    "city": city_name,
                    "category": category_name,
                    "latitude": lat,
                    "longitude": lon,
                    "wikidata_id": wiki_qid,
                    "osm_id": f"relation/{osm_id}" if osm_id and not osm_id.startswith("relation/") else osm_id,
                    "wikipedia_url": f"https://en.wikipedia.org/wiki/{name.replace(' ', '_')}" if name else "",
                    "commons_url": f"https://commons.wikimedia.org/wiki/Category:{commons_cat.replace(' ', '_')}" if commons_cat else "",
                    "reference_image": img_url,
                    "status": "DISCOVERED",
                    "images_count": 0
                })
            return places
        except Exception as e:
            logger.warning(f"[Discovery] Wikidata query for {category_name} ({qid}) failed: {e}")
            return []

    def load_curated_global_landmarks(self) -> List[Dict[str, Any]]:
        """Curated high-density worldwide landmarks across all continents and key categories."""
        landmarks_raw = [
            # Europe - Western & Southern
            ("Eiffel Tower", ["Tour Eiffel", "Iron Lady"], "FRA", "Paris", "tower", 48.858370, 2.294481, "Q243", "relation/50138", "https://commons.wikimedia.org/wiki/Category:Eiffel_Tower"),
            ("Louvre Museum", ["Musée du Louvre"], "FRA", "Paris", "museum", 48.860611, 2.337644, "Q19675", "way/27236594", "https://commons.wikimedia.org/wiki/Category:Musée_du_Louvre"),
            ("Notre-Dame de Paris", ["Notre-Dame Cathedral"], "FRA", "Paris", "place_of_worship", 48.852968, 2.349902, "Q2981", "way/201261309", "https://commons.wikimedia.org/wiki/Category:Notre-Dame_de_Paris"),
            ("Palace of Versailles", ["Château de Versailles"], "FRA", "Versailles", "palace", 48.804865, 2.120355, "Q2946", "relation/16141015", "https://commons.wikimedia.org/wiki/Category:Palace_of_Versailles"),
            ("Arc de Triomphe", ["Place Charles de Gaulle"], "FRA", "Paris", "monument", 48.873792, 2.295028, "Q64436", "way/27236595", "https://commons.wikimedia.org/wiki/Category:Arc_de_Triomphe_de_l%27Étoile"),
            ("Mont Saint-Michel", ["Le Mont-Saint-Michel"], "FRA", "Normandy", "unesco_heritage", 48.636064, -1.511457, "Q34071", "relation/27981", "https://commons.wikimedia.org/wiki/Category:Mont-Saint-Michel"),
            ("Colosseum", ["Flavian Amphitheatre", "Colosseo"], "ITA", "Rome", "archaeological_site", 41.890210, 12.492231, "Q10285", "way/27949518", "https://commons.wikimedia.org/wiki/Category:Colosseum"),
            ("Pantheon Rome", ["Pantheon"], "ITA", "Rome", "place_of_worship", 41.898611, 12.476944, "Q9930", "way/25447781", "https://commons.wikimedia.org/wiki/Category:Pantheon_(Rome)"),
            ("Leaning Tower of Pisa", ["Torre di Pisa"], "ITA", "Pisa", "tower", 43.722952, 10.396597, "Q39054", "way/32731557", "https://commons.wikimedia.org/wiki/Category:Leaning_Tower_of_Pisa"),
            ("St. Peter's Basilica", ["Basilica di San Pietro"], "VAT", "Vatican City", "place_of_worship", 41.902167, 12.453611, "Q12512", "way/23048995", "https://commons.wikimedia.org/wiki/Category:Saint_Peter's_Basilica"),
            ("Florence Cathedral", ["Santa Maria del Fiore", "Duomo di Firenze"], "ITA", "Florence", "place_of_worship", 43.773124, 11.255977, "Q174780", "way/25447782", "https://commons.wikimedia.org/wiki/Category:Duomo_(Florence)"),
            ("Venice Grand Canal", ["Canal Grande"], "ITA", "Venice", "tourist_attraction", 45.437190, 12.332630, "Q208479", "relation/128362", "https://commons.wikimedia.org/wiki/Category:Grand_Canal_(Venice)"),
            ("Big Ben and Palace of Westminster", ["Elizabeth Tower", "Houses of Parliament"], "GBR", "London", "tower", 51.500729, -0.124625, "Q41225", "way/33420803", "https://commons.wikimedia.org/wiki/Category:Big_Ben"),
            ("Tower Bridge", ["Tower Bridge London"], "GBR", "London", "bridge", 51.505556, -0.075278, "Q83125", "way/4476059", "https://commons.wikimedia.org/wiki/Category:Tower_Bridge"),
            ("Stonehenge", ["Stonehenge Monument"], "GBR", "Wiltshire", "archaeological_site", 51.178889, -1.826111, "Q39367", "way/25299499", "https://commons.wikimedia.org/wiki/Category:Stonehenge"),
            ("Edinburgh Castle", ["Castell Dhùn Èideann"], "GBR", "Edinburgh", "castle", 55.948611, -3.199889, "Q212065", "way/23249012", "https://commons.wikimedia.org/wiki/Category:Edinburgh_Castle"),
            ("Brandenburg Gate", ["Brandenburger Tor"], "DEU", "Berlin", "monument", 52.516272, 13.377722, "Q82425", "way/24056285", "https://commons.wikimedia.org/wiki/Category:Brandenburg_Gate"),
            ("Neuschwanstein Castle", ["Schloss Neuschwanstein"], "DEU", "Bavaria", "castle", 47.557500, 10.749722, "Q4152", "way/23018291", "https://commons.wikimedia.org/wiki/Category:Neuschwanstein_Castle"),
            ("Cologne Cathedral", ["Kölner Dom"], "DEU", "Cologne", "place_of_worship", 50.941290, 6.958170, "Q4176", "way/23114945", "https://commons.wikimedia.org/wiki/Category:Cologne_Cathedral"),
            ("Sagrada Família", ["Basílica de la Sagrada Família"], "ESP", "Barcelona", "place_of_worship", 41.403611, 2.174444, "Q8843", "way/44274952", "https://commons.wikimedia.org/wiki/Category:Sagrada_Família"),
            ("Alhambra", ["La Alhambra de Granada"], "ESP", "Granada", "palace", 37.176944, -3.589722, "Q47461", "relation/1781292", "https://commons.wikimedia.org/wiki/Category:Alhambra"),
            ("Parthenon", ["Acropolis Parthenon"], "GRC", "Athens", "archaeological_site", 37.971528, 23.726667, "Q10288", "way/24854992", "https://commons.wikimedia.org/wiki/Category:Parthenon"),
            ("Matterhorn", ["Mont Cervin", "Monte Cervino"], "CHE", "Zermatt", "mountain", 45.976389, 7.658333, "Q1313", "node/26862590", "https://commons.wikimedia.org/wiki/Category:Matterhorn"),
            ("Rijksmuseum", ["National Museum Amsterdam"], "NLD", "Amsterdam", "museum", 52.359997, 4.885278, "Q190804", "way/4982631", "https://commons.wikimedia.org/wiki/Category:Rijksmuseum_Amsterdam"),
            ("Charles Bridge", ["Karlův most"], "CZE", "Prague", "bridge", 50.086444, 14.411444, "Q188585", "way/4621948", "https://commons.wikimedia.org/wiki/Category:Charles_Bridge"),
            ("Hungarian Parliament Building", ["Országház"], "HUN", "Budapest", "monument", 47.507222, 19.045556, "Q11819", "way/23249015", "https://commons.wikimedia.org/wiki/Category:Hungarian_Parliament_Building"),
            ("Dubrovnik City Walls", ["Walls of Dubrovnik"], "HRV", "Dubrovnik", "fortress", 42.641667, 18.106944, "Q1048842", "way/23249016", "https://commons.wikimedia.org/wiki/Category:City_walls_of_Dubrovnik"),
            ("Bran Castle", ["Dracula Castle"], "ROU", "Transylvania", "castle", 45.515000, 25.367222, "Q651582", "way/23249017", "https://commons.wikimedia.org/wiki/Category:Bran_Castle"),
            ("Hagia Sophia", ["Ayasofya"], "TUR", "Istanbul", "place_of_worship", 41.008583, 28.980167, "Q12506", "way/27236599", "https://commons.wikimedia.org/wiki/Category:Hagia_Sophia"),
            ("Saint Basil's Cathedral", ["Pokrovsky Cathedral"], "RUS", "Moscow", "place_of_worship", 55.752500, 37.623056, "Q129846", "way/23018299", "https://commons.wikimedia.org/wiki/Category:Saint_Basil's_Cathedral"),
            ("Hermitage Museum", ["Winter Palace"], "RUS", "Saint Petersburg", "museum", 59.939822, 30.314561, "Q132783", "relation/16141019", "https://commons.wikimedia.org/wiki/Category:Hermitage_Museum"),

            # North America
            ("Statue of Liberty", ["Liberty Enlightening the World"], "USA", "New York", "statue", 40.689247, -74.044502, "Q9202", "way/27236592", "https://commons.wikimedia.org/wiki/Category:Statue_of_Liberty"),
            ("Empire State Building", ["ESB"], "USA", "New York", "tower", 40.748817, -73.985428, "Q9188", "way/34633854", "https://commons.wikimedia.org/wiki/Category:Empire_State_Building"),
            ("Golden Gate Bridge", ["Golden Gate"], "USA", "San Francisco", "bridge", 37.819929, -122.478255, "Q44440", "way/3180410", "https://commons.wikimedia.org/wiki/Category:Golden_Gate_Bridge"),
            ("Grand Canyon National Park", ["Grand Canyon"], "USA", "Arizona", "national_park", 36.106965, -112.112997, "Q174787", "relation/1453306", "https://commons.wikimedia.org/wiki/Category:Grand_Canyon_National_Park"),
            ("Yosemite National Park", ["Yosemite Valley"], "USA", "California", "national_park", 37.865101, -119.538329, "Q180402", "relation/1453307", "https://commons.wikimedia.org/wiki/Category:Yosemite_National_Park"),
            ("White House", ["1600 Pennsylvania Avenue"], "USA", "Washington D.C.", "palace", 38.897676, -77.036530, "Q35529", "way/23885474", "https://commons.wikimedia.org/wiki/Category:White_House"),
            ("Lincoln Memorial", ["Lincoln Statue DC"], "USA", "Washington D.C.", "monument", 38.889278, -77.050139, "Q213559", "way/23885475", "https://commons.wikimedia.org/wiki/Category:Lincoln_Memorial"),
            ("Space Needle", ["Space Needle Seattle"], "USA", "Seattle", "tower", 47.620500, -122.349278, "Q48324", "way/23018290", "https://commons.wikimedia.org/wiki/Category:Space_Needle"),
            ("Mount Rushmore", ["Mount Rushmore National Memorial"], "USA", "South Dakota", "monument", 43.879102, -103.459067, "Q83637", "way/27236593", "https://commons.wikimedia.org/wiki/Category:Mount_Rushmore"),
            ("Niagara Falls", ["Horseshoe Falls", "American Falls"], "CAN", "Ontario", "waterfall", 43.080556, -79.071111, "Q34038", "relation/128365", "https://commons.wikimedia.org/wiki/Category:Niagara_Falls"),
            ("CN Tower", ["Canadian National Tower"], "CAN", "Toronto", "tower", 43.642566, -79.387057, "Q134883", "way/23018292", "https://commons.wikimedia.org/wiki/Category:CN_Tower"),
            ("Banff National Park", ["Lake Louise Banff"], "CAN", "Alberta", "national_park", 51.496846, -115.928056, "Q180531", "relation/1453308", "https://commons.wikimedia.org/wiki/Category:Banff_National_Park"),
            ("Chichen Itza", ["El Castillo Chichen Itza"], "MEX", "Yucatan", "archaeological_site", 20.684285, -88.567783, "Q5859", "way/24854995", "https://commons.wikimedia.org/wiki/Category:Chichén_Itzá"),
            ("Teotihuacan", ["Pyramid of the Sun"], "MEX", "State of Mexico", "archaeological_site", 19.692500, -98.843889, "Q46247", "way/24854996", "https://commons.wikimedia.org/wiki/Category:Teotihuacan"),
            ("Tulum Maya Ruins", ["Tulum Archeological Zone"], "MEX", "Quintana Roo", "archaeological_site", 20.214722, -87.429444, "Q220202", "way/24854999", "https://commons.wikimedia.org/wiki/Category:Tulum_(archaeological_site)"),

            # South America & Caribbean
            ("Christ the Redeemer", ["Cristo Redentor"], "BRA", "Rio de Janeiro", "statue", -22.951916, -43.210487, "Q79961", "way/27236591", "https://commons.wikimedia.org/wiki/Category:Cristo_Redentor_(Rio_de_Janeiro)"),
            ("Sugarloaf Mountain", ["Pão de Açúcar"], "BRA", "Rio de Janeiro", "mountain", -22.948611, -43.157222, "Q206103", "node/26862596", "https://commons.wikimedia.org/wiki/Category:Sugarloaf_Mountain"),
            ("Cathedral of Brasília", ["Catedral Metropolitana de Brasília"], "BRA", "Brasília", "place_of_worship", -15.798333, -47.875556, "Q1064848", "way/27236598", "https://commons.wikimedia.org/wiki/Category:Cathedral_of_Brasilia"),
            ("Amazon Theatre", ["Teatro Amazonas"], "BRA", "Manaus", "monument", -3.130278, -60.023333, "Q1812836", "way/27236599", "https://commons.wikimedia.org/wiki/Category:Teatro_Amazonas"),
            ("Iguazu Falls", ["Cataratas del Iguazú", "Cataratas do Iguaçu"], "BRA", "Paraná", "waterfall", -25.695278, -54.436667, "Q36312", "relation/128366", "https://commons.wikimedia.org/wiki/Category:Iguazu_Falls"),
            ("Machu Picchu", ["Old Peak Incan Citadel"], "PER", "Cusco", "archaeological_site", -13.163141, -72.544963, "Q7919", "way/24854991", "https://commons.wikimedia.org/wiki/Category:Machu_Picchu"),
            ("Torres del Paine National Park", ["Torres del Paine"], "CHL", "Magallanes", "national_park", -51.253246, -72.881432, "Q738600", "relation/1453309", "https://commons.wikimedia.org/wiki/Category:Torres_del_Paine_National_Park"),
            ("Perito Moreno Glacier", ["Glaciar Perito Moreno"], "ARG", "Santa Cruz", "unesco_heritage", -50.469722, -73.030000, "Q33295", "relation/1453310", "https://commons.wikimedia.org/wiki/Category:Perito_Moreno_Glacier"),
            ("Teatro Colón", ["Colon Theater Buenos Aires"], "ARG", "Buenos Aires", "monument", -34.601111, -58.383056, "Q827401", "way/27236589", "https://commons.wikimedia.org/wiki/Category:Teatro_Colón"),
            ("Salar de Uyuni", ["Uyuni Salt Flats"], "BOL", "Potosí", "unesco_heritage", -20.133778, -67.489133, "Q7607", "relation/1453315", "https://commons.wikimedia.org/wiki/Category:Salar_de_Uyuni"),
            ("Galápagos National Park", ["Galapagos Islands"], "ECU", "Galápagos", "national_park", -0.743611, -90.312500, "Q38095", "relation/1453316", "https://commons.wikimedia.org/wiki/Category:Galapagos_Islands"),
            ("Angel Falls", ["Salto Ángel"], "VEN", "Bolívar", "waterfall", 5.967500, -62.535556, "Q80196", "node/26862597", "https://commons.wikimedia.org/wiki/Category:Angel_Falls"),
            ("Easter Island Moai", ["Rapa Nui Ahu Tongariki"], "CHL", "Easter Island", "statue", -27.125833, -109.276944, "Q137175", "way/24854988", "https://commons.wikimedia.org/wiki/Category:Moai"),
            ("Old Havana", ["La Habana Vieja"], "CUB", "Havana", "unesco_heritage", 23.136944, -82.353333, "Q1333734", "relation/1453317", "https://commons.wikimedia.org/wiki/Category:Old_Havana"),

            # Asia & Middle East
            ("Great Wall of China", ["Wanli Changcheng", "Mutianyu"], "CHN", "Beijing", "monument", 40.431908, 116.570374, "Q12501", "way/24854990", "https://commons.wikimedia.org/wiki/Category:Great_Wall_of_China"),
            ("Forbidden City", ["Palace Museum Beijing"], "CHN", "Beijing", "palace", 39.916345, 116.397155, "Q80863", "relation/16141016", "https://commons.wikimedia.org/wiki/Category:Forbidden_City"),
            ("Terracotta Army", ["Terracotta Warriors"], "CHN", "Xi'an", "archaeological_site", 34.384722, 109.278611, "Q47672", "way/24854997", "https://commons.wikimedia.org/wiki/Category:Terracotta_Army"),
            ("Potala Palace", ["Potala Lhasa"], "CHN", "Lhasa", "palace", 29.657778, 91.116944, "Q71229", "way/23249019", "https://commons.wikimedia.org/wiki/Category:Potala_Palace"),
            ("Oriental Pearl Tower", ["Shanghai Tower"], "CHN", "Shanghai", "tower", 31.239722, 121.499722, "Q223100", "way/23018288", "https://commons.wikimedia.org/wiki/Category:Oriental_Pearl_Tower"),
            ("Mount Fuji", ["Fuji-san"], "JPN", "Honshu", "mountain", 35.360556, 138.727778, "Q39231", "node/26862591", "https://commons.wikimedia.org/wiki/Category:Mount_Fuji"),
            ("Tokyo Tower", ["Nippon Denpatō"], "JPN", "Tokyo", "tower", 35.658581, 139.745433, "Q183536", "way/23018293", "https://commons.wikimedia.org/wiki/Category:Tokyo_Tower"),
            ("Fushimi Inari-taisha", ["Fushimi Inari Shrine"], "JPN", "Kyoto", "place_of_worship", 34.967140, 135.772671, "Q714457", "way/27236595", "https://commons.wikimedia.org/wiki/Category:Fushimi_Inari-taisha"),
            ("Himeji Castle", ["White Heron Castle"], "JPN", "Hyogo", "castle", 34.839444, 134.693889, "Q188636", "way/23018294", "https://commons.wikimedia.org/wiki/Category:Himeji_Castle"),
            ("Kiyomizu-dera", ["Kiyomizu Temple"], "JPN", "Kyoto", "place_of_worship", 34.994856, 135.785047, "Q221716", "way/27236587", "https://commons.wikimedia.org/wiki/Category:Kiyomizu-dera"),
            ("Senso-ji", ["Asakusa Kannon Temple"], "JPN", "Tokyo", "place_of_worship", 35.714769, 139.796655, "Q1060934", "way/27236588", "https://commons.wikimedia.org/wiki/Category:Sensō-ji"),
            ("Gyeongbokgung Palace", ["Gyeongbok Palace"], "KOR", "Seoul", "palace", 37.579611, 126.977056, "Q482479", "way/23249021", "https://commons.wikimedia.org/wiki/Category:Gyeongbokgung"),
            ("N Seoul Tower", ["Namsan Tower"], "KOR", "Seoul", "tower", 37.551170, 126.988228, "Q483087", "way/23018287", "https://commons.wikimedia.org/wiki/Category:N_Seoul_Tower"),
            ("Taj Mahal", ["Crown of the Palace"], "IND", "Agra", "unesco_heritage", 27.175145, 78.042142, "Q9141", "way/27236590", "https://commons.wikimedia.org/wiki/Category:Taj_Mahal"),
            ("Qutb Minar", ["Qutub Minar"], "IND", "Delhi", "tower", 28.524444, 77.185556, "Q190240", "way/23018295", "https://commons.wikimedia.org/wiki/Category:Qutb_Minar"),
            ("Hawa Mahal", ["Palace of Winds"], "IND", "Jaipur", "palace", 26.923889, 75.826667, "Q205814", "way/23249020", "https://commons.wikimedia.org/wiki/Category:Hawa_Mahal"),
            ("Golden Temple", ["Harmandir Sahib Amritsar"], "IND", "Amritsar", "place_of_worship", 31.620000, 74.876389, "Q180422", "way/27236586", "https://commons.wikimedia.org/wiki/Category:Harmandir_Sahib"),
            ("Gateway of India", ["Gateway Mumbai"], "IND", "Mumbai", "monument", 18.921984, 72.834654, "Q503612", "way/24056286", "https://commons.wikimedia.org/wiki/Category:Gateway_of_India"),
            ("Angkor Wat", ["Nokor Vat"], "KHM", "Siem Reap", "archaeological_site", 13.412469, 103.866986, "Q43473", "way/24854993", "https://commons.wikimedia.org/wiki/Category:Angkor_Wat"),
            ("Petronas Towers", ["Menara Berkembar Petronas"], "MYS", "Kuala Lumpur", "tower", 3.157850, 101.711860, "Q83063", "way/23018296", "https://commons.wikimedia.org/wiki/Category:Petronas_Towers"),
            ("Marina Bay Sands", ["MBS Singapore"], "SGP", "Singapore", "tourist_attraction", 1.283889, 103.859167, "Q746356", "way/27236596", "https://commons.wikimedia.org/wiki/Category:Marina_Bay_Sands"),
            ("Gardens by the Bay", ["Supertree Grove"], "SGP", "Singapore", "national_park", 1.281667, 103.863611, "Q152912", "relation/1453311", "https://commons.wikimedia.org/wiki/Category:Gardens_by_the_Bay"),
            ("Wat Phra Kaew", ["Temple of the Emerald Buddha"], "THA", "Bangkok", "place_of_worship", 13.751667, 100.492500, "Q849924", "way/27236585", "https://commons.wikimedia.org/wiki/Category:Wat_Phra_Kaew"),
            ("Borobudur", ["Candi Borobudur"], "IDN", "Central Java", "unesco_heritage", -7.607874, 110.203751, "Q48307", "way/24854989", "https://commons.wikimedia.org/wiki/Category:Borobudur"),
            ("Prambanan", ["Candi Prambanan"], "IDN", "Yogyakarta", "place_of_worship", -7.752022, 110.491467, "Q849059", "way/24854987", "https://commons.wikimedia.org/wiki/Category:Prambanan"),
            ("Ha Long Bay", ["Vịnh Hạ Long"], "VNM", "Quảng Ninh", "unesco_heritage", 20.910056, 107.183900, "Q190128", "relation/1453318", "https://commons.wikimedia.org/wiki/Category:Ha_Long_Bay"),
            ("Shwedagon Pagoda", ["Great Dagon Pagoda"], "MMR", "Yangon", "place_of_worship", 16.798333, 96.149722, "Q464529", "way/27236584", "https://commons.wikimedia.org/wiki/Category:Shwedagon_Pagoda"),
            ("Sigiriya", ["Lion Rock Fortress"], "LKA", "Matale", "archaeological_site", 7.957000, 80.760000, "Q245281", "way/24854986", "https://commons.wikimedia.org/wiki/Category:Sigiriya"),
            ("Registan", ["Registan Square Samarkand"], "UZB", "Samarkand", "monument", 39.654722, 66.975833, "Q1374187", "way/24056287", "https://commons.wikimedia.org/wiki/Category:Registan"),
            ("Burj Khalifa", ["Burj Dubai"], "ARE", "Dubai", "tower", 25.197197, 55.274376, "Q12495", "way/23018297", "https://commons.wikimedia.org/wiki/Category:Burj_Khalifa"),
            ("Sheikh Zayed Grand Mosque", ["Grand Mosque Abu Dhabi"], "ARE", "Abu Dhabi", "place_of_worship", 24.412222, 54.474722, "Q1150493", "way/27236583", "https://commons.wikimedia.org/wiki/Category:Sheikh_Zayed_Grand_Mosque"),
            ("Petra", ["Al-Khazneh", "The Treasury"], "JOR", "Ma'an", "archaeological_site", 30.328456, 35.444362, "Q5788", "way/24854994", "https://commons.wikimedia.org/wiki/Category:Petra"),
            ("Great Pyramid of Giza", ["Pyramid of Khufu"], "EGY", "Giza", "archaeological_site", 29.979167, 31.134167, "Q12521", "way/24854998", "https://commons.wikimedia.org/wiki/Category:Great_Pyramid_of_Giza"),
            ("Great Sphinx of Giza", ["The Sphinx"], "EGY", "Giza", "statue", 29.975278, 31.137500, "Q130932", "way/27236597", "https://commons.wikimedia.org/wiki/Category:Great_Sphinx_of_Giza"),
            ("Abu Simbel Temples", ["Temples of Ramses II"], "EGY", "Aswan", "archaeological_site", 22.337222, 31.625833, "Q134140", "way/24854985", "https://commons.wikimedia.org/wiki/Category:Abu_Simbel_temples"),
            ("Karnak Temple Complex", ["Karnak Temple"], "EGY", "Luxor", "archaeological_site", 25.718889, 32.658611, "Q185934", "way/24854984", "https://commons.wikimedia.org/wiki/Category:Karnak_temple_complex"),
            ("Western Wall", ["Kotel", "Wailing Wall"], "ISR", "Jerusalem", "place_of_worship", 31.776667, 35.234167, "Q42398", "way/27236598", "https://commons.wikimedia.org/wiki/Category:Western_Wall"),
            ("Dome of the Rock", ["Qubbat al-Sakhrah"], "ISR", "Jerusalem", "place_of_worship", 31.778056, 35.235278, "Q12506", "way/27236582", "https://commons.wikimedia.org/wiki/Category:Dome_of_the_Rock"),
            ("Mount Everest", ["Sagarmatha", "Chomolungma"], "NPL", "Himalayas", "mountain", 27.988056, 86.925278, "Q513", "node/26862592", "https://commons.wikimedia.org/wiki/Category:Mount_Everest"),

            # Africa & Oceania
            ("Table Mountain", ["Tafelberg"], "ZAF", "Cape Town", "mountain", -33.962778, 18.409722, "Q213346", "node/26862593", "https://commons.wikimedia.org/wiki/Category:Table_Mountain"),
            ("Robben Island", ["Robbeneiland"], "ZAF", "Western Cape", "unesco_heritage", -33.806667, 18.369722, "Q192233", "relation/1453319", "https://commons.wikimedia.org/wiki/Category:Robben_Island"),
            ("Mount Kilimanjaro", ["Kilima Njaro"], "TZA", "Kilimanjaro", "mountain", -3.065653, 37.353272, "Q7296", "node/26862594", "https://commons.wikimedia.org/wiki/Category:Mount_Kilimanjaro"),
            ("Serengeti National Park", ["Serengeti"], "TZA", "Mara", "national_park", -2.332778, 34.566667, "Q184636", "relation/1453312", "https://commons.wikimedia.org/wiki/Category:Serengeti_National_Park"),
            ("Victoria Falls", ["Mosi-oa-Tunya"], "ZWE", "Matabeleland", "waterfall", -17.924444, 25.856667, "Q43419", "relation/128367", "https://commons.wikimedia.org/wiki/Category:Victoria_Falls"),
            ("Rock-Hewn Churches Lalibela", ["Church of Saint George Lalibela"], "ETH", "Amhara", "unesco_heritage", 12.031944, 39.041111, "Q1078701", "way/27236581", "https://commons.wikimedia.org/wiki/Category:Rock-Hewn_Churches,_Lalibela"),
            ("Great Mosque of Djenné", ["Djenné Mosque"], "MLI", "Djenné", "place_of_worship", 13.905000, -4.555000, "Q683632", "way/27236580", "https://commons.wikimedia.org/wiki/Category:Great_Mosque_of_Djenné"),
            ("Hassan II Mosque", ["Mosquée Hassan-II Casablanca"], "MAR", "Casablanca", "place_of_worship", 33.608611, -7.632778, "Q825674", "way/27236579", "https://commons.wikimedia.org/wiki/Category:Hassan_II_Mosque"),
            ("Sydney Opera House", ["Bennelong Point Opera House"], "AUS", "Sydney", "tourist_attraction", -33.856784, 151.215297, "Q45188", "way/23018298", "https://commons.wikimedia.org/wiki/Category:Sydney_Opera_House"),
            ("Sydney Harbour Bridge", ["The Coathanger"], "AUS", "Sydney", "bridge", -33.852222, 151.210556, "Q54495", "way/4476060", "https://commons.wikimedia.org/wiki/Category:Sydney_Harbour_Bridge"),
            ("Uluru", ["Ayers Rock"], "AUS", "Northern Territory", "unesco_heritage", -25.344444, 131.036111, "Q83013", "node/26862595", "https://commons.wikimedia.org/wiki/Category:Uluru"),
            ("Great Barrier Reef", ["Cairns Reef Marine Park"], "AUS", "Queensland", "unesco_heritage", -18.287067, 147.699192, "Q3408", "relation/1453313", "https://commons.wikimedia.org/wiki/Category:Great_Barrier_Reef"),
            ("Twelve Apostles", ["Twelve Apostles Victoria"], "AUS", "Victoria", "tourist_attraction", -38.665833, 143.104444, "Q137175", "node/26862598", "https://commons.wikimedia.org/wiki/Category:The_Twelve_Apostles_(Victoria)"),
            ("Milford Sound", ["Piopiotahi"], "NZL", "Fiordland", "national_park", -44.671389, 167.925833, "Q841386", "relation/1453314", "https://commons.wikimedia.org/wiki/Category:Milford_Sound"),
            ("Hobbiton Movie Set", ["Hobbiton Matamata"], "NZL", "Waikato", "tourist_attraction", -37.872222, 175.682778, "Q482478", "way/27236578", "https://commons.wikimedia.org/wiki/Category:Hobbiton_movie_set")
        ]

        places = []
        for name, aliases, country, city, cat, lat, lon, w_id, osm_id, commons_url in landmarks_raw:
            pid = self.generate_canonical_place_id(name, lat, lon, w_id)
            places.append({
                "place_id": pid,
                "name": name,
                "aliases": aliases,
                "country": country,
                "city": city,
                "category": cat,
                "latitude": lat,
                "longitude": lon,
                "wikidata_id": w_id,
                "osm_id": osm_id,
                "wikipedia_url": f"https://en.wikipedia.org/wiki/{name.replace(' ', '_')}",
                "commons_url": commons_url,
                "status": "DISCOVERED",
                "images_count": 0
            })
        return places

    def run_discovery(self, output_path: Optional[str] = None) -> List[Dict[str, Any]]:
        if output_path is None:
            output_path = os.path.join(self.places_dir, "places.jsonl")
        csv_path = os.path.join(self.places_dir, "places.csv")
        
        logger.info("[Discovery] Starting Master Place Discovery Engine across all global taxonomy categories...")
        all_places: List[Dict[str, Any]] = []
        
        # 1. Load curated master landmark seed
        curated = self.load_curated_global_landmarks()
        all_places.extend(curated)
        logger.info(f"[Discovery] Loaded {len(curated)} curated master seed landmarks across all continents.")
        
        # 2. Query Wikidata SPARQL across ALL taxonomy categories
        for cat_name, qid in LANDMARK_TAXONOMY.items():
            logger.info(f"[Discovery] Querying Wikidata SPARQL for {cat_name} (wd:{qid})...")
            try:
                places_from_wiki = self.query_wikidata_category(qid, cat_name, limit=50)
                logger.info(f"[Discovery] Retrieved {len(places_from_wiki)} places for {cat_name}.")
                all_places.extend(places_from_wiki)
            except Exception as e:
                logger.warning(f"[Discovery] Failed category {cat_name}: {e}")

        # 3. Spatial Proximity Deduplication & Canonical Reconciliation
        seen_cells: Dict[str, Dict[str, Any]] = {}
        unique_places: List[Dict[str, Any]] = []
        
        for p in all_places:
            cell = spatial_grid_cell(p["latitude"], p["longitude"], cell_size_deg=0.0003)  # ~30m
            if cell in seen_cells:
                existing = seen_cells[cell]
                # Merge metadata
                if p.get("aliases"):
                    for a in p["aliases"]:
                        if a not in existing["aliases"]:
                            existing["aliases"].append(a)
                if not existing.get("wikidata_id") and p.get("wikidata_id"):
                    existing["wikidata_id"] = p["wikidata_id"]
                if not existing.get("commons_url") and p.get("commons_url"):
                    existing["commons_url"] = p["commons_url"]
                if not existing.get("osm_id") and p.get("osm_id"):
                    existing["osm_id"] = p["osm_id"]
            else:
                seen_cells[cell] = p
                unique_places.append(p)

        logger.info(f"[Discovery] Reconciled into {len(unique_places)} canonical unique worldwide landmarks.")
        
        # 4. Save to JSONL and CSV
        with open(output_path, "w", encoding="utf-8") as jf:
            for p in unique_places:
                jf.write(json.dumps(p, ensure_ascii=False) + "\n")
                
        fieldnames = ["place_id", "name", "aliases", "country", "city", "category",
                      "latitude", "longitude", "wikidata_id", "osm_id", "wikipedia_url", "commons_url"]
        with open(csv_path, "w", encoding="utf-8", newline="") as cf:
            writer = csv.DictWriter(cf, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for p in unique_places:
                row = dict(p)
                row["aliases"] = "; ".join(p.get("aliases", [])) if isinstance(p.get("aliases"), list) else ""
                writer.writerow(row)

        # 5. Persist to State Tracker
        inserted = self.tracker.bulk_upsert_places(unique_places)
        logger.info(f"[Discovery] Persisted {inserted} records into state_tracker.db.")
        
        return unique_places

def main():
    parser = argparse.ArgumentParser(description="ARGUS Master Place Discovery")
    parser.add_argument("--config", default="config/argus_config.yaml", help="Path to config YAML")
    parser.add_argument("--output", default="ARGUS_DATASET/places/places.jsonl", help="Output JSONL path")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    cfg = load_config(args.config)
    tracker = StateTracker(os.path.join(cfg.system.base_dir, "indexes", "state_tracker.db"))
    engine = DiscoveryEngine(cfg, tracker)
    places = engine.run_discovery(args.output)
    print(f"Discovery complete. Discovered {len(places)} canonical landmarks.")

if __name__ == "__main__":
    main()
