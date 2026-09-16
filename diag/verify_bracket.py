import sys
sys.path.insert(0, 'C:/Users/33393/Desktop/ai-legal-helper/backend')
from scripts.capture_eval import _extract_citations, _case_laws_for_sentence

text = '根据[民法典 第六百八十条]禁止高利放贷，借款合同的利率不得违反国家有关规定。根据[民法典 第六百六十八条]，借款合同应当采用书面形式。'
print('citations:', sorted(_extract_citations(text)))
law_ids = ['民法典:680', '民法典:668', '民法典:577']
print('case_laws:', _case_laws_for_sentence('根据[民法典 第六百八十条]禁止高利放贷。', law_ids))

# 回归：主格式《》仍正常
text2 = '根据《民法典》第五百八十五条规定，约定的违约金过分高于造成的损失的，人民法院或者仲裁机构可以根据当事人的请求予以适当减少。'
print('book citations:', sorted(_extract_citations(text2)))
print('book case_laws:', _case_laws_for_sentence(text2, ['民法典:585', '民法典:584']))