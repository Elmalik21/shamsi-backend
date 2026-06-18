import urllib.request, json
req = urllib.request.Request('http://localhost:8000/api/v1/export/e5887c80/pdf/', data=json.dumps({'ai_result':{'pareto_solutions':[{'panel_count':30,'system_kw':10}]}}).encode('utf-8'), headers={'Content-Type': 'application/json'})
try:
    urllib.request.urlopen(req)
except Exception as e:
    print(e.read().decode('utf-8'))
