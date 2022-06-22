import io
import csv

import xlsxwriter
from fastapi import FastAPI, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse
import httpx


URL = "https://www.cbr-xml-daily.ru/daily_json.js"


app = FastAPI()


app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


async def get_external_api_data():
    """
    Request external API and return json data
    :return:
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(URL)
        response.raise_for_status()

    return response.json()


@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, })


@app.get("/currencies")
async def get_currencies():
    data = await get_external_api_data()
    return {currency.get('CharCode'): currency.get('Name') for currency in data.get('Valute').values()}


@app.get("/currency/rates")
async def get_rates(currencies: list = Query(default=[])):
    if len(currencies) == 0:
        return []

    data = await get_external_api_data()
    return [
        {'code': element.get('CharCode'), 'name': element.get('Name'), 'value': element.get('Value'),
         'date': data.get('Date'), 'nominal': element.get('Nominal')}
        for element in data.get('Valute').values() if element.get('CharCode') in currencies
    ]


@app.get("/download_xlsx", response_description='xlsx')
async def download_xlsx(currencies: list = Query(default=[])):
    raw_data = await get_external_api_data()

    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output)
    worksheet = workbook.add_worksheet()
    worksheet.write(0, 0, 'Код валюты')
    worksheet.write(0, 1, 'Название валюты')
    worksheet.write(0, 2, 'Цена')
    worksheet.write(0, 3, 'Дата котировки')
    worksheet.write(0, 4, 'Номинал')

    index = 1
    for element in raw_data.get('Valute').values():
        if element.get('CharCode') in currencies:
            worksheet.write(index, 0, element.get('CharCode'))
            worksheet.write(index, 1, element.get('Name'))
            worksheet.write(index, 2, element.get('Value'))
            worksheet.write(index, 3, raw_data.get('Date'))
            worksheet.write(index, 4, element.get('Nominal'))
            index += 1
    workbook.close()
    output.seek(0)

    return StreamingResponse(output,
                             media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                             headers={"Content-Disposition": 'attachment; filename="currency_rates.xlsx"'})


@app.get("/download_csv")
async def download_xlsx(currencies: list = Query(default=[])):
    raw_data = await get_external_api_data()

    sio = io.StringIO()
    csv.writer(sio).writerow(['Код валюты', 'Название валюты', 'Цена', 'Дата котировки', 'Номинал'])

    for element in raw_data.get('Valute').values():
        if element.get('CharCode') in currencies:
            csv.writer(sio).writerow([element.get('CharCode'), element.get('Name'),
                                      element.get('Value'), raw_data.get('Date'), element.get('Nominal')])

    bio = io.BytesIO()
    bio.write(sio.getvalue().encode('windows-1251'))
    bio.seek(0)

    return StreamingResponse(bio, headers={"Content-Disposition": 'attachment; filename="currency_rates.csv"'})
