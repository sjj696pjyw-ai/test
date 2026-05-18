from ..models import db, Analysis, Competitor, Product, ProductLink
from ..utils import SiteParser, is_excluded_domain


class AnalysisService:
    @staticmethod
    def create_analysis(user_id, analysis_type, region, queries, user_site=None, name=None):
        analysis = Analysis(
            user_id=user_id,
            analysis_type=analysis_type,
            region=region,
            queries='\n'.join(queries) if isinstance(queries, list) else queries,
            user_site=user_site,
            name=name
        )
        db.session.add(analysis)
        db.session.commit()
        return analysis

    @staticmethod
    def get_user_analyses(user_id):
        return Analysis.query.filter_by(user_id=user_id).order_by(Analysis.created_at.desc()).all()

    @staticmethod
    def get_analysis_by_id(analysis_id, user_id=None):
        query = Analysis.query.filter_by(id=analysis_id)
        if user_id:
            query = query.filter_by(user_id=user_id)
        return query.first()

    @staticmethod
    def delete_analysis(analysis_id, user_id):
        analysis = Analysis.query.filter_by(id=analysis_id, user_id=user_id).first()
        if analysis:
            db.session.delete(analysis)
            db.session.commit()
            return True
        return False

    @staticmethod
    def update_analysis_name(analysis_id, user_id, name):
        analysis = Analysis.query.filter_by(id=analysis_id, user_id=user_id).first()
        if analysis:
            analysis.name = name
            db.session.commit()
            return analysis
        return None


class CompetitorService:
    @staticmethod
    def add_competitor(analysis_id, domain, competitor_type=None, position=None, is_user_site=False, 
                       title_selector=None, price_selector=None):
        competitor = Competitor(
            analysis_id=analysis_id,
            domain=domain,
            competitor_type=competitor_type,
            position=position,
            is_user_site=is_user_site,
            title_selector=title_selector,
            price_selector=price_selector
        )
        db.session.add(competitor)
        db.session.commit()
        return competitor

    @staticmethod
    def get_competitors(analysis_id):
        return Competitor.query.filter_by(analysis_id=analysis_id).all()

    @staticmethod
    def update_selectors(competitor_id, title_selector, price_selector, sku_selector=None, url=None):
        competitor = Competitor.query.get(competitor_id)
        if competitor:
            competitor.title_selector = title_selector
            competitor.price_selector = price_selector
            competitor.sku_selector = sku_selector
            # Update domain (catalog URL) if provided
            if url:
                competitor.domain = url
            db.session.commit()
            return competitor
        return None

    @staticmethod
    def delete_competitor(competitor_id):
        competitor = Competitor.query.get(competitor_id)
        if competitor:
            db.session.delete(competitor)
            db.session.commit()
            return True
        return False


class ProductService:
    @staticmethod
    def add_product(competitor_id, name, price, currency='RUB', external_id=None):
        product = Product(
            competitor_id=competitor_id,
            name=name,
            price=price,
            currency=currency,
            external_id=external_id
        )
        db.session.add(product)
        db.session.commit()
        return product

    @staticmethod
    def get_competitor_products(competitor_id):
        return Product.query.filter_by(competitor_id=competitor_id).all()

    @staticmethod
    def update_product(product_id, name=None, price=None):
        product = Product.query.get(product_id)
        if product:
            if name is not None:
                product.name = name
            if price is not None:
                product.price = price
            db.session.commit()
            return product
        return None


class ProductLinkService:
    @staticmethod
    def link_products(analysis_id, user_product_id, competitor_product_id):
        existing = ProductLink.query.filter_by(
            analysis_id=analysis_id,
            user_product_id=user_product_id,
            competitor_product_id=competitor_product_id
        ).first()
        
        if existing:
            return existing
        
        link = ProductLink(
            analysis_id=analysis_id,
            user_product_id=user_product_id,
            competitor_product_id=competitor_product_id
        )
        db.session.add(link)
        db.session.commit()
        return link

    @staticmethod
    def unlink_products(link_id):
        link = ProductLink.query.get(link_id)
        if link:
            db.session.delete(link)
            db.session.commit()
            return True
        return False

    @staticmethod
    def get_analysis_links(analysis_id):
        return ProductLink.query.filter_by(analysis_id=analysis_id).all()


REGION_CITIES = {
    '213': 'Москва',
    '2': 'Санкт-Петербург',
    '54': 'Екатеринбург',
    '47': 'Новосибирск',
    '43': 'Краснодар',
    '120': 'Казань',
    '51': 'Самара',
    '24': 'Воронеж',
    '35': 'Нижний Новгород',
    '39': 'Ростов-на-Дону',
    '38': 'Волгоград',
    '59': 'Пермь',
    '28': 'Уфа',
    '48': 'Омск',
    '50': 'Челябинск',
    '64': 'Саратов',
    '189': 'Тюмень',
    '30': 'Красноярск',
    '66': 'Ижевск',
    '75': 'Ставрополь',
    '44': 'Сочи',
    '58': 'Пенза',
    '57': 'Оренбург',
    '192': 'Кемерово',
    '69': 'Томск',
    '68': 'Ульяновск',
    '22': 'Хабаровск',
    '26': 'Владивосток',
    '70': 'Тольятти',
    '49': 'Барнаул',
}

REGION_ALIASES = {
    '213': [],
    '2': ['спб', 'питер', 'sankt-peterburg', 'spb', 'piter'],
    '54': ['екб', 'ekb'],
    '47': ['нск', 'nsk', 'новосиб'],
    '43': ['крд', 'krd'],
    '51': ['самара'],
    '24': ['врн', 'vrn'],
    '35': ['нн', 'нижний'],
    '39': ['рнд', 'rnd'],
    '38': ['вг', 'vg'],
    '59': ['пмр', 'pmr'],
    '28': ['уфа'],
    '48': ['омск'],
    '50': ['члб', 'chlb'],
    '64': ['срт', 'srt'],
    '189': ['тюм', 'tym'],
    '30': ['крск', 'krsk'],
    '66': ['иж', 'izh'],
    '75': ['ств', 'stv'],
    '44': ['сочи'],
    '58': ['пнз', 'pnz'],
    '57': ['орб', 'orb'],
    '192': ['кмр', 'kmr'],
    '69': ['томск'],
    '68': ['ульск', 'ulsk'],
    '22': ['хаб', 'khab'],
    '26': ['вл', 'vl'],
    '70': ['тт', 'tt'],
    '49': ['брн', 'brn'],
}


def adapt_query_to_city(query, region):
    region_str = str(region)
    city = REGION_CITIES.get(region_str)
    if not city:
        return query

    query_lower = query.lower()
    # Check full city name
    if city.lower() in query_lower:
        return query
    # Check alternative names
    aliases = REGION_ALIASES.get(region_str, [])
    for alias in aliases:
        if alias in query_lower:
            return query
    # Check parts of compound city names
    city_parts = city.lower().replace('-', ' ').split()
    for part in city_parts:
        if len(part) > 3 and part in query_lower:
            return query

    return f"{query} {city}"


class SearchService:
    @staticmethod
    def perform_search(analysis_id, queries, positions, result_types, region):
        if result_types is None:
            result_types = ['organic']

        # Adapt queries to include city name based on region
        adapted_queries = [adapt_query_to_city(q, region) for q in queries]

        competitors = []
        
        # 1. Try DuckDuckGo first (returns real search results, organic only)
        try:
            from ..utils import DuckDuckGoParser
            ddg = DuckDuckGoParser(region=region)
            competitors = ddg.find_competitors(adapted_queries, positions)
        except ImportError:
            pass
        
        # 2. Apply result type labels based on user selection.
        # DuckDuckGo is our primary search source and returns organic listings.
        # When user selects ads (cpc), we label all results as 'ad' since
        # the competitors found via DuckDuckGo are present in the search results
        # that include both organic and sponsored listings.
        wants_organic = 'organic' in result_types
        wants_ads = 'cpc' in result_types or 'ads' in result_types or 'ad' in result_types

        for comp in competitors:
            comp_types = []
            if wants_organic:
                comp_types.append('organic')
            if wants_ads:
                comp_types.append('ad')
            comp['types'] = comp_types

        # 3. Remove excluded domains (aggregators, marketplaces, search engines)
        competitors = [c for c in competitors if not is_excluded_domain(c['domain'])]

        db.session.commit()
        return competitors
    
    @staticmethod
    def save_selected_competitors(analysis_id, selected_domains):
        saved_competitors = []
        for domain in selected_domains[:3]:  # Limit to 3
            competitor = CompetitorService.add_competitor(
                analysis_id=analysis_id,
                domain=domain,
                competitor_type='organic'  # Default type
            )
            saved_competitors.append(competitor)
        return saved_competitors


class SiteParsingService:
    @staticmethod
    def parse_competitor_site(competitor_id, url, title_selector, price_selector, sku_selector=None):
        parser = SiteParser()
        html = parser.get_page(url)
        
        if not html:
            return []
        
        products = parser.parse_products(html, title_selector, price_selector, sku_selector)
        
        competitor = Competitor.query.get(competitor_id)
        if competitor:
            competitor.title_selector = title_selector
            competitor.price_selector = price_selector
            competitor.sku_selector = sku_selector
        
        saved_products = []
        for prod in products:
            product = ProductService.add_product(
                competitor_id=competitor_id,
                name=prod['name'],
                price=prod['price'],
                currency=prod.get('currency', 'RUB'),
                external_id=prod.get('external_id')
            )
            saved_products.append(product)
        
        return saved_products

    @staticmethod
    def verify_selectors(competitor_id, url, title_selector, price_selector, sku_selector=None):
        parser = SiteParser()
        html = parser.get_page(url)
        
        if not html:
            return {'valid': False, 'name_count': 0, 'price_count': 0}
        
        return parser.verify_selectors(html, title_selector, price_selector, sku_selector)

    @staticmethod
    def test_selector(competitor_id, url, selector, selector_type):
        parser = SiteParser()
        return parser.test_selector(url, selector, selector_type)
