ШІ Яна - http://ec2-3-64-165-239.eu-central-1.compute.amazonaws.com/

Паролі можно дізнатись у організаторів Хакатону


update 24.11.25 - v2 -  https://github.com/010io/Yana.Diia_v3, https://yana-diia-v3.vercel.app/

update 30.11.25 - v1 new - http://ec2-63-176-139-155.eu-central-1.compute.amazonaws.com/v1

# Запуск в середовищі розробки
## Сервер
1. ```cmd
    pip install -r requirements.txt
    ```
1. ```cmd
    touch server/.env
    echo 'CODEMIE_USERNAME=' >> server/.env
    echo 'CODEMIE_PASSWORD=' >> server/.env
    echo 'OPENAI_API_KEY=' >> server/.env
    ```
1. Додайте відповідні значення в server/.env
1. Запуск серверу
```cmd
cd server
python application.py
```

## UI
1. В корні проекту виконати
```cmd
npm i
```
1. За потреби модифікуйте .env в корні аби показував на API сервер
```cmd
NEXT_PUBLIC_API_HOST=
NEXT_PUBLIC_USERNAME=
NEXT_PUBLIC_PASSWORD=
```
1. Запуск UI
```cmd
npm run dev
```