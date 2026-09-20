NEWS_SOURCES = {
    "INTERNATIONAL": {
        "rss": [
            "https://www.reuters.com/rssFeed/worldNews",
            "https://apnews.com/hub/ap-top-news?rss=1",
            "https://www.aljazeera.com/xml/rss/all.xml",
            "https://feeds.bbci.co.uk/news/world/rss.xml",
            "https://www.dw.com/en/top-stories/rss",
            "https://www.france24.com/en/rss",
            "https://news.un.org/feed/subscribe/en/news/all/rss.xml",
            "https://globalvoices.org/feed/",
            "https://world.einnews.com/rss"
        ],
        "api": [
            "https://newsapi.org/v2/top-headlines",
            "https://api.worldnewsapi.com/search-news",
            "https://newsdata.io/api/1/news"
        ]
    },
    "USA": {
        "rss": [
            "https://rss.cnn.com/rss/edition.rss",
            "https://feeds.nbcnews.com/nbcnews/public/news",
            "https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml",
            "https://feeds.foxnews.com/foxnews/latest",
            "https://feeds.washingtonpost.com/rss/world",
            "https://abcnews.go.com/abcnews/topstories",
            "https://www.cbsnews.com/latest/rss/main",
            "https://www.usatoday.com/rss/news/",
            "https://apnews.com/apf-topnews?rss=1"
        ],
        "api": [
            "https://newsapi.org/v2/top-headlines?country=us"
        ]
    },
    "INDIA": {
        "rss": [
            "https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
            "https://www.thehindu.com/news/national/feeder/default.rss",
            "https://www.hindustantimes.com/feeds/rss/india-news/rssfeed.xml",
            "https://indianexpress.com/feed/",
            "https://feeds.ndtv.com/ndtvnews-top-stories",
            "https://scroll.in/feed",
            "https://theprint.in/feed/",
            "https://economictimes.indiatimes.com/rssfeedstopstories.cms",
            "https://www.deccanherald.com/rss.xml"
        ],
        "api": [
            "https://newsapi.org/v2/top-headlines?country=in",
            "https://newsdata.io/api/1/news?country=in"
        ]
    },
    "EUROPE": {
        "rss": [
            "https://feeds.bbci.co.uk/news/world/europe/rss.xml",
            "https://www.euronews.com/rss",
            "https://www.theguardian.com/world/rss",
            "https://www.spiegel.de/international/index.rss",
            "https://www.lemonde.fr/rss/une.xml",
            "https://elpais.com/rss/feed.html",
            "https://www.repubblica.it/rss/homepage/rss2.0.xml",
            "https://www.ft.com/rss/home",
            "https://www.politico.eu/rss",
            "https://rss.dw.com/xml/rss-en-eu"
        ],
        "api": []
    },
    "AFRICA": {
        "rss": [
            "https://allafrica.com/tools/headlines/rdf/latest/headlines.rdf",
            "https://www.news24.com/rss",
            "https://nation.africa/kenya/rss",
            "https://mg.co.za/feed/",
            "https://www.theafricareport.com/feed/",
            "https://www.premiumtimesng.com/feed",
            "https://www.sabcnews.com/sabcnews/feed/",
            "https://www.egyptindependent.com/feed/",
            "https://www.newtimes.co.rw/rss"
        ],
        "api": []
    },
    "UAE": {
        "rss": [
            "https://gulfnews.com/rss",
            "https://www.khaleejtimes.com/rss",
            "https://www.thenationalnews.com/rss",
            "https://www.arabianbusiness.com/rss",
            "https://www.emirates247.com/rss",
            "https://www.albayan.ae/rss",
            "https://www.itihad.ae/rss",
            "https://www.zawya.com/rss"
        ],
        "api": [
            "https://newsapi.org/v2/top-headlines?country=ae"
        ]
    },
    "IRAN": {
        "rss": [
            "https://www.presstv.ir/rss",
            "https://www.tehrantimes.com/rss",
            "https://www.irna.ir/rss",
            "https://en.mehrnews.com/rss",
            "https://www.tasnimnews.com/en/rss",
            "https://farsnews.ir/rss",
            "https://www.radiofarda.com/rss",
            "https://www.isna.ir/rss"
        ],
        "api": []
    },
    "CHINA": {
        "rss": [
            "http://www.xinhuanet.com/english/rss/worldrss.xml",
            "https://www.chinadaily.com.cn/rss/world_rss.xml",
            "https://www.globaltimes.cn/rss/world.xml",
            "https://www.scmp.com/rss/91/feed",
            "https://news.cgtn.com/rss",
            "https://english.people.com.cn/rss/World.xml",
            "https://www.shine.cn/rss/",
            "https://www.beijingreview.com.cn/rss/"
        ],
        "api": []
    },
    "RUSSIA": {
        "rss": [
            "https://tass.com/rss/v2.xml",
            "https://ria.ru/export/rss2/archive/index.xml",
            "https://www.interfax.ru/rss.asp",
            "https://www.themoscowtimes.com/rss",
            "https://www.rt.com/rss/news/",
            "https://www.kommersant.ru/RSS/news.xml",
            "https://novayagazeta.eu/rss",
            "https://www.vedomosti.ru/rss/news"
        ],
        "api": []
    },
    "JAPAN": {
        "rss": [
            "https://www3.nhk.or.jp/rss/news/cat0.xml",
            "https://www.japantimes.co.jp/feed/",
            "https://www.asahi.com/rss/asahi/newsheadlines.rdf",
            "https://www.yomiuri.co.jp/rss/world.xml",
            "https://mainichi.jp/rss/etc/mainichi-flash.rss",
            "https://english.kyodonews.net/rss/news.xml",
            "https://asia.nikkei.com/rss/feed/nar",
            "https://japantoday.com/feed"
        ],
        "api": []
    },
    "AUSTRALIA": {
        "rss": [
            "https://www.abc.net.au/news/feed/51120/rss.xml",
            "https://www.theaustralian.com.au/rss",
            "https://www.smh.com.au/rss/feed.xml",
            "https://www.theguardian.com/au/rss",
            "https://www.news.com.au/rss",
            "https://www.theage.com.au/rss/feed.xml",
            "https://www.afr.com/rss",
            "https://www.sbs.com.au/news/feed"
        ],
        "api": []
    },
    "TAIWAN": {
        "rss": [
            "https://www.taipeitimes.com/xml/rss",
            "https://focustaiwan.tw/rss",
            "https://www.chinapost.com.tw/rss",
            "https://news.ltn.com.tw/rss",
            "https://udn.com/rssfeed/news/2/6638",
            "https://www.ettoday.net/news/rss_all.xml",
            "https://news.tvbs.com.tw/rss",
            "https://www.storm.mg/feeds"
        ],
        "api": []
    },
    "SOUTH_KOREA": {
        "rss": [
            "https://en.yna.co.kr/rss/news.xml",
            "https://www.koreaherald.com/rss",
            "https://www.koreatimes.co.kr/www/rss/rss.xml",
            "https://www.arirang.com/rss/news.xml",
            "https://world.kbs.co.kr/rss/rss_news.htm",
            "https://koreajoongangdaily.joins.com/rss",
            "https://www.chosun.com/arc/outboundfeeds/rss/",
            "https://www.hani.co.kr/rss/"
        ],
        "api": []
    },
    "ISRAEL": {
        "rss": [
            "https://www.haaretz.com/rss",
            "https://www.jpost.com/rss/rssfeedsfrontpage.aspx",
            "https://www.timesofisrael.com/feed/",
            "https://www.ynetnews.com/category/3082",
            "https://www.themarker.com/cmlink/1.144",
            "https://www.israelhayom.com/feed/",
            "https://www.inn.co.il/Rss.aspx",
            "https://www.globes.co.il/webservice/rss/rssfeeder.asmx/FeederNode",
            "https://www.i24news.tv/en/rss"
        ],
        "api": []
    }
}
