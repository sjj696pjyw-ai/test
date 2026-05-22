from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
import requests
import os
import json
from ..models import db, Competitor
from ..services import (
    AnalysisService, CompetitorService, ProductService,
    ProductLinkService, SiteParsingService, PriceUpdateService
)
from ..utils.domains import is_excluded_domain

analysis_bp = Blueprint('analysis', __name__, url_prefix='/api/analysis')


@analysis_bp.route('', methods=['POST'])
@jwt_required()
def create_analysis():
    current_user_id = get_jwt_identity()
    data = request.get_json()

    if not data:
        return jsonify({'error': 'No data provided'}), 400

    analysis_type = data.get('type')
    region = data.get('region')
    name = data.get('name')

    if not analysis_type or not region:
        return jsonify({'error': 'Analysis type and region are required'}), 400

    user_analyses = AnalysisService.get_user_analyses(current_user_id)
    user_analyses_count = len(user_analyses) if user_analyses else 0
    default_name = f"Анализ #{user_analyses_count + 1}"
    analysis_name = name if name else default_name

    if analysis_type == 'manual':
        user_site = data.get('user_site')
        competitors = data.get('competitors', [])

        if not user_site:
            return jsonify({'error': 'User site is required for manual analysis'}), 400

        analysis = AnalysisService.create_analysis(
            user_id=current_user_id,
            analysis_type='manual',
            region=region,
            queries=[],
            name=analysis_name
        )

        user_competitor = CompetitorService.add_competitor(
            analysis_id=analysis.id,
            domain=user_site,
            is_user_site=True
        )

        saved_competitors = [user_competitor]

        for comp in competitors[:3]:
            domain = comp.get('domain')
            if domain and is_excluded_domain(domain):
                continue
            competitor = CompetitorService.add_competitor(
                analysis_id=analysis.id,
                domain=domain,
                is_user_site=False
            )
            saved_competitors.append(competitor)

        return jsonify({
            'message': 'Analysis created successfully',
            'analysis': analysis.to_dict(),
            'competitors': [c.to_dict() for c in saved_competitors]
        }), 201

    return jsonify({'error': 'Invalid analysis type'}), 400


@analysis_bp.route('', methods=['GET'])
@jwt_required()
def get_analyses():
    current_user_id = get_jwt_identity()
    analyses = AnalysisService.get_user_analyses(current_user_id)
    
    return jsonify({
        'analyses': [a.to_dict() for a in analyses]
    }), 200


@analysis_bp.route('/<int:analysis_id>', methods=['GET'])
@jwt_required()
def get_analysis(analysis_id):
    current_user_id = get_jwt_identity()
    analysis = AnalysisService.get_analysis_by_id(analysis_id, current_user_id)
    
    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404
    
    competitors = CompetitorService.get_competitors(analysis_id)
    product_links = ProductLinkService.get_analysis_links(analysis_id)
    
    result = analysis.to_dict()
    result['competitors'] = []
    
    for comp in competitors:
        comp_dict = comp.to_dict()
        products = ProductService.get_competitor_products(comp.id)
        comp_dict['products'] = [p.to_dict() for p in products]
        result['competitors'].append(comp_dict)
    
    result['product_links'] = [link.to_dict() for link in product_links]
    
    return jsonify({'analysis': result}), 200


@analysis_bp.route('/<int:analysis_id>/name', methods=['PUT'])
@jwt_required()
def update_analysis_name(analysis_id):
    current_user_id = get_jwt_identity()
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Name is required'}), 400
    
    new_name = data.get('name')
    
    analysis = AnalysisService.update_analysis_name(analysis_id, current_user_id, new_name)
    
    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404
    
    return jsonify({
        'message': 'Analysis name updated successfully',
        'analysis': analysis.to_dict()
    }), 200


@analysis_bp.route('/<int:analysis_id>', methods=['DELETE'])
@jwt_required()
def delete_analysis(analysis_id):
    current_user_id = get_jwt_identity()
    
    if AnalysisService.delete_analysis(analysis_id, current_user_id):
        return jsonify({'message': 'Analysis deleted successfully'}), 200
    
    return jsonify({'error': 'Analysis not found'}), 404


@analysis_bp.route('/<int:analysis_id>/competitor', methods=['POST'])
@jwt_required()
def add_competitor(analysis_id):
    current_user_id = get_jwt_identity()
    analysis = AnalysisService.get_analysis_by_id(analysis_id, current_user_id)
    
    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404
    
    data = request.get_json()
    domain = data.get('domain')
    
    if not domain:
        return jsonify({'error': 'Domain is required'}), 400
    
    is_user_site = data.get('is_user_site', False)
    competitor = CompetitorService.add_competitor(
        analysis_id=analysis_id,
        domain=domain,
        is_user_site=is_user_site
    )
    
    return jsonify({
        'message': 'Competitor added successfully',
        'competitor': competitor.to_dict()
    }), 201


@analysis_bp.route('/competitor/<int:competitor_id>', methods=['GET'])
@jwt_required()
def get_competitor(competitor_id):
    competitor = Competitor.query.get(competitor_id)
    
    if not competitor:
        return jsonify({'error': 'Competitor not found'}), 404
    
    return jsonify({'competitor': competitor.to_dict()}), 200


@analysis_bp.route('/competitor/<int:competitor_id>', methods=['PUT'])
@jwt_required()
def update_competitor(competitor_id):
    data = request.get_json()
    
    title_selector = data.get('title_selector')
    price_selector = data.get('price_selector')
    url = data.get('url')
    
    competitor = CompetitorService.update_selectors(competitor_id, title_selector, price_selector, url)
    
    if not competitor:
        return jsonify({'error': 'Competitor not found'}), 404
    
    return jsonify({
        'message': 'Competitor updated successfully',
        'competitor': competitor.to_dict()
    }), 200


@analysis_bp.route('/competitor/<int:competitor_id>/reparse', methods=['POST'])
@jwt_required()
def reparse_competitor(competitor_id):
    current_user_id = get_jwt_identity()
    competitor = Competitor.query.get(competitor_id)
    
    if not competitor:
        return jsonify({'error': 'Конкурент не найден'}), 404
    
    analysis = AnalysisService.get_analysis_by_id(competitor.analysis_id, current_user_id)
    if not analysis:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    data = request.get_json()
    url = data.get('url')
    title_selector = data.get('title_selector')
    price_selector = data.get('price_selector')
    
    if not all([url, title_selector, price_selector]):
        return jsonify({'error': 'URL и селекторы обязательны'}), 400
    
    competitor.title_selector = title_selector
    competitor.price_selector = price_selector
    if url:
        competitor.domain = url
    
    db.session.commit()
    
    products = SiteParsingService.parse_competitor_site(
        competitor_id=competitor_id,
        url=url,
        title_selector=title_selector,
        price_selector=price_selector
    )
    
    return jsonify({
        'message': 'Селекторы обновлены и товары собраны',
        'competitor': competitor.to_dict(),
        'products': [p.to_dict() for p in products]
    }), 200


@analysis_bp.route('/competitor/<int:competitor_id>', methods=['DELETE'])
@jwt_required()
def delete_competitor(competitor_id):
    if CompetitorService.delete_competitor(competitor_id):
        return jsonify({'message': 'Competitor deleted successfully'}), 200
    
    return jsonify({'error': 'Competitor not found'}), 404


@analysis_bp.route('/competitor/<int:competitor_id>/parse', methods=['POST'])
@jwt_required()
def parse_competitor(competitor_id):
    data = request.get_json()
    
    url = data.get('url')
    title_selector = data.get('title_selector')
    price_selector = data.get('price_selector')
    
    if not all([url, title_selector, price_selector]):
        return jsonify({'error': 'URL and selectors are required'}), 400
    
    products = SiteParsingService.parse_competitor_site(
        competitor_id=competitor_id,
        url=url,
        title_selector=title_selector,
        price_selector=price_selector
    )
    
    return jsonify({
        'message': 'Products parsed successfully',
        'products': [p.to_dict() for p in products]
    }), 200


@analysis_bp.route('/competitor/<int:competitor_id>/verify-selectors', methods=['POST'])
@jwt_required()
def verify_selectors(competitor_id):
    competitor = Competitor.query.get(competitor_id)
    if not competitor:
        return jsonify({'error': 'Competitor not found'}), 404
    
    data = request.get_json()
    url = data.get('url')
    title_selector = data.get('title_selector')
    price_selector = data.get('price_selector')
    
    result = SiteParsingService.verify_selectors(
        competitor_id=competitor_id,
        url=url,
        title_selector=title_selector,
        price_selector=price_selector
    )
    
    return jsonify(result), 200


@analysis_bp.route('/link', methods=['POST'])
@jwt_required()
def link_products():
    data = request.get_json()
    
    analysis_id = data.get('analysis_id')
    user_product_id = data.get('user_product_id')
    competitor_product_id = data.get('competitor_product_id')
    
    if not all([analysis_id, user_product_id, competitor_product_id]):
        return jsonify({'error': 'All IDs are required'}), 400
    
    link = ProductLinkService.link_products(
        analysis_id=analysis_id,
        user_product_id=user_product_id,
        competitor_product_id=competitor_product_id
    )
    
    return jsonify({
        'message': 'Products linked successfully',
        'link': link.to_dict()
    }), 201


@analysis_bp.route('/unlink/<int:link_id>', methods=['DELETE'])
@jwt_required()
def unlink_products(link_id):
    if ProductLinkService.unlink_products(link_id):
        return jsonify({'message': 'Products unlinked successfully'}), 200
    
    return jsonify({'error': 'Link not found'}), 404


@analysis_bp.route('/<int:analysis_id>/update-prices', methods=['POST'])
@jwt_required()
def update_analysis_prices(analysis_id):
    current_user_id = get_jwt_identity()
    analysis = AnalysisService.get_analysis_by_id(analysis_id, current_user_id)
    
    if not analysis:
        return jsonify({'error': 'Анализ не найден'}), 404
    
    result = PriceUpdateService.update_analysis_prices(analysis_id)
    
    if result['success']:
        status_code = 200
        message = 'Цены успешно обновлены'
        if result.get('partial_count', 0) > 0:
            message = f"Обновлены цены по {result['success_count']} конкурентам, по {result['partial_count']} - частично"
    else:
        status_code = 400
        message = result.get('error', 'Ошибка обновления цен')
    
    return jsonify({
        'message': message,
        'result': result
    }), status_code


@analysis_bp.route('/competitor/<int:competitor_id>/update-prices', methods=['POST'])
@jwt_required()
def update_competitor_prices(competitor_id):
    competitor = Competitor.query.get(competitor_id)
    
    if not competitor:
        return jsonify({'error': 'Конкурент не найден'}), 404
    
    current_user_id = get_jwt_identity()
    analysis = AnalysisService.get_analysis_by_id(competitor.analysis_id, current_user_id)
    
    if not analysis:
        return jsonify({'error': 'Доступ запрещен'}), 403
    
    result = PriceUpdateService.update_competitor_prices(competitor_id)
    
    if result['success']:
        status_code = 200
        message = 'Цены успешно обновлены'
    elif result.get('status') == 'rate_limited':
        status_code = 429
        message = result.get('error', 'Слишком частые запросы')
    else:
        status_code = 400
        message = result.get('error', 'Ошибка обновления цен')
    
    return jsonify({
        'message': message,
        'result': result
    }), status_code


@analysis_bp.route('/<int:analysis_id>/price-dynamics', methods=['GET'])
@jwt_required()
def get_price_dynamics(analysis_id):
    current_user_id = get_jwt_identity()
    analysis = AnalysisService.get_analysis_by_id(analysis_id, current_user_id)
    
    if not analysis:
        return jsonify({'error': 'Анализ не найден'}), 404
    
    days = request.args.get('days', 30, type=int)
    dynamics = PriceUpdateService.get_analysis_price_dynamics(analysis_id, days)
    
    return jsonify({
        'dynamics': dynamics,
        'days': days
    }), 200


@analysis_bp.route('/check-site', methods=['POST'])
@jwt_required()
def check_site():
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'available': False, 'message': 'URL не указан'}), 400
    
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    from ..utils.domains import extract_domain
    domain = extract_domain(url)
    if is_excluded_domain(domain):
        return jsonify({
            'available': False, 
            'message': 'Сайт относится к агрегаторам/маркетплейсам/мессенджерам/поисковикам',
            'is_excluded': True
        }), 200
    
    try:
        response = requests.get(
            url,
            timeout=10,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        if response.status_code == 200:
            return jsonify({'available': True, 'message': 'Сайт доступен'}), 200
        else:
            return jsonify({
                'available': False, 
                'message': f'Сайт вернул код {response.status_code}'
            }), 200
    except requests.exceptions.Timeout:
        return jsonify({'available': False, 'message': 'Превышен таймаут подключения'}), 200
    except requests.exceptions.ConnectionError:
        return jsonify({'available': False, 'message': 'Ошибка подключения к сайту'}), 200
    except Exception as e:
        return jsonify({'available': False, 'message': f'Ошибка: {str(e)}'}), 200


@analysis_bp.route('/<int:analysis_id>/report', methods=['GET'])
@jwt_required()
def get_report(analysis_id):
    current_user_id = get_jwt_identity()
    analysis = AnalysisService.get_analysis_by_id(analysis_id, current_user_id)
    
    if not analysis:
        return jsonify({'error': 'Analysis not found'}), 404
    
    competitors = CompetitorService.get_competitors(analysis_id)
    product_links = ProductLinkService.get_analysis_links(analysis_id)
    
    report = {
        'analysis_id': analysis.id,
        'created_at': analysis.created_at.isoformat(),
        'region': analysis.region,
        'data': []
    }
    
    for link in product_links:
        user_prod = link.user_product
        comp_prod = link.competitor_product
        
        if user_prod and comp_prod:
            competitor = next((c for c in competitors if c.id == comp_prod.competitor_id), None)
            
            price_diff = None
            if user_prod.price and comp_prod.price:
                price_diff = comp_prod.price - user_prod.price
            
            report['data'].append({
                'competitor': competitor.domain if competitor else 'Unknown',
                'user_price': user_prod.price,
                'competitor_price': comp_prod.price,
                'price_difference': price_diff,
                'user_product': user_prod.name,
                'competitor_product': comp_prod.name
            })
    
    return jsonify({'report': report}), 200
