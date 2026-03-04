#!/usr/bin/env python3
# extract_financial_terms.py
# Extract key financial terms and concepts from transcript for stock selection formula

import json
import sys
import re
from collections import Counter

FINANCIAL_KEYWORDS = {
    'technical': ['支撑位', '阻力位', 'MACD', 'KDJ', 'RSI', '布林带', '均线', '金叉', '死叉', '背离'],
    'fundamental': ['PE', 'PB', 'ROE', '营收', '净利润', '毛利率', '现金流', '负债率'],
    'market': ['牛市', '熊市', '震荡', '板块轮动', '资金流向', '主力资金', '北向资金'],
    'trading': ['止损', '止盈', '仓位', '分批建仓', '高抛低吸', '趋势线', '突破'],
    'industry': ['新能源', '光伏', '半导体', '医药', '消费', '金融', '周期股']
}

def extract_terms(transcript_data):
    """Extract financial terms from transcript"""
    all_text = ' '.join([item['text'] for item in transcript_data])
    
    term_counts = Counter()
    
    # Search for keywords
    for category, keywords in FINANCIAL_KEYWORDS.items():
        for keyword in keywords:
            count = all_text.count(keyword)
            if count > 0:
                term_counts[keyword] = count
    
    # Extract patterns like "XX%上涨" or "目标价XX元"
    percentage_pattern = r'(\d+\.?\d*)%'
    price_pattern = r'目标价\s*(\d+\.?\d*)\s*元'
    support_resistance = r'(支撑位|阻力位)\s*[:：]\s*(\d+\.?\d*)'
    
    percentages = re.findall(percentage_pattern, all_text)
    prices = re.findall(price_pattern, all_text)
    supports = re.findall(support_resistance, all_text)
    
    return {
        'term_counts': dict(term_counts),
        'percentages': percentages,
        'price_targets': prices,
        'support_levels': supports,
        'total_words': len(all_text.split())
    }

def main():
    if len(sys.argv) != 2:
        print("Usage: python extract_financial_terms.py <transcript_json>")
        sys.exit(1)
    
    json_file = sys.argv[1]
    
    try:
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        transcript_data = data.get('transcript', [])
        analysis = extract_terms(transcript_data)
        
        # Generate output
        output_file = json_file.replace('.json', '_analysis.json')
        
        result = {
            'video_id': data.get('video_id', 'unknown'),
            'analysis_timestamp': '2026-02-28T12:00:00Z',
            'financial_analysis': analysis,
            'recommendations': []
        }
        
        # Generate basic recommendations based on analysis
        if analysis['term_counts'].get('支撑位') or analysis['term_counts'].get('阻力位'):
            result['recommendations'].append('Consider adding support/resistance level alerts to stock monitoring')
        
        if analysis['term_counts'].get('MACD') or analysis['term_counts'].get('金叉'):
            result['recommendations'].append('MACD-based trend signals could be integrated into trend_trading_analyzer.py')
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        
        print(f"Financial term analysis completed!")
        print(f"Output: {output_file}")
        print(f"Found {sum(analysis['term_counts'].values())} financial terms")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()