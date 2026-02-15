import asyncio
import os

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

ADMIN_IDS = [
    695804108,   # ты
    414880465    # второй админ
]

PRICE_PER_M2 = 80
PRICE_PER_WINDOW = 400
COMMISSION_RATE = 0.20

bot = Bot(token=TOKEN)
dp = Dispatcher()

users = {}
orders_by_user = {}
orders_by_id = {}
user_messages = {}
ORDER_SEQ = 1


def commission(price):
    return int(price * COMMISSION_RATE)


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="➕ Новая заявка")],
            [KeyboardButton(text="📋 Мои заявки")]
        ],
        resize_keyboard=True
    )


def admin_kb(order_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Выполнено",
                    callback_data=f"done:{order_id}"
                ),
                InlineKeyboardButton(
                    text="❌ Отменено",
                    callback_data=f"cancel:{order_id}"
                )
            ]
        ]
    )


def save_msg(uid, mid):
    user_messages.setdefault(uid, []).append(mid)


# ---------------- START ----------------

@dp.message(Command("start"))
async def start(message: types.Message):
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Уборка квартиры")],
            [KeyboardButton(text="Мытьё окон")],
            [KeyboardButton(text="Уборка квартиры + Мытьё окон")]
        ],
        resize_keyboard=True
    )

    msg = await message.answer(
        "Здравствуйте! Выберите услугу:",
        reply_markup=kb
    )
    save_msg(message.from_user.id, msg.message_id)


# ---------------- МЕНЮ ----------------

@dp.message(F.text == "➕ Новая заявка")
async def new_order(message: types.Message):
    users.pop(message.from_user.id, None)
    await start(message)


@dp.message(F.text == "📋 Мои заявки")
async def my_orders(message: types.Message):
    uid = message.from_user.id

    if uid not in orders_by_user or not orders_by_user[uid]:
        await message.answer("У вас пока нет заявок.", reply_markup=main_menu())
        return

    text = "📋 Ваши заявки:\n\n"

    for i, order_id in enumerate(orders_by_user[uid], 1):
        o = orders_by_id[order_id]
        text += (
            f"{i}. {o['service']}\n"
            f"Адрес: {o['address']}\n"
            f"Время: {o['time']}\n"
            f"Сумма: {o['price']} ₽\n"
            f"Статус: {o['status']}\n\n"
        )

    await message.answer(text, reply_markup=main_menu())


# ---------------- ВЫБОР УСЛУГ ----------------

@dp.message(F.text == "Уборка квартиры")
async def clean(message: types.Message):
    users[message.from_user.id] = {"service": "Уборка квартиры", "step": "m2"}
    msg = await message.answer("Введите площадь квартиры в м².")
    save_msg(message.from_user.id, msg.message_id)


@dp.message(F.text == "Мытьё окон")
async def windows(message: types.Message):
    users[message.from_user.id] = {"service": "Мытьё окон", "step": "windows"}
    msg = await message.answer("Введите количество окон.")
    save_msg(message.from_user.id, msg.message_id)


@dp.message(F.text == "Уборка квартиры + Мытьё окон")
async def combo(message: types.Message):
    users[message.from_user.id] = {"service": "Уборка квартиры + Мытьё окон", "step": "m2"}
    msg = await message.answer("Введите площадь квартиры в м².")
    save_msg(message.from_user.id, msg.message_id)


# ---------------- КОНТАКТ ----------------

@dp.message(F.contact)
async def phone_handler(message: types.Message):
    global ORDER_SEQ

    uid = message.from_user.id
    save_msg(uid, message.message_id)

    if uid not in users:
        return

    data = users[uid]
    phone = message.contact.phone_number

    total = data["price"]
    com = commission(total)

    order_id = ORDER_SEQ
    ORDER_SEQ += 1

    order = {
        "id": order_id,
        "user_id": uid,
        "service": data["service"],
        "price": total,
        "commission": com,
        "address": data["address"],
        "time": data["time"],
        "m2": data.get("m2"),
        "windows": data.get("windows"),
        "phone": phone,
        "status": "ожидает"
    }

    orders_by_id[order_id] = order
    orders_by_user.setdefault(uid, []).append(order_id)

    admin_text = (
        f"🆕 Заявка №{order_id}\n\n"
        f"Услуга: {order['service']}\n"
        f"Сумма: {order['price']} ₽\n"
        f"Комиссия: {order['commission']} ₽\n"
        f"Исполнителю: {order['price'] - order['commission']} ₽\n\n"
        f"Площадь: {order.get('m2','-')}\n"
        f"Окон: {order.get('windows','-')}\n"
        f"Адрес: {order['address']}\n"
        f"Время: {order['time']}\n"
        f"Телефон: {order['phone']}\n\n"
        f"Клиент ID: {uid}"
    )

    for admin in ADMIN_IDS:
        await bot.send_message(admin, admin_text, reply_markup=admin_kb(order_id))

    # очистка диалога
    for mid in user_messages.get(uid, []):
        try:
            await bot.delete_message(uid, mid)
        except:
            pass

    user_messages[uid] = []

    await message.answer(
        "✅ Ваша заявка принята.",
        reply_markup=main_menu()
    )

    users.pop(uid, None)


# ---------------- ШАГИ ----------------

@dp.message(F.text)
async def steps(message: types.Message):
    uid = message.from_user.id
    save_msg(uid, message.message_id)

    if uid not in users:
        return

    data = users[uid]
    step = data["step"]

    if step == "m2":
        try:
            m2 = int(message.text)
            if m2 <= 0:
                raise ValueError
        except:
            msg = await message.answer("Введите площадь числом.")
            save_msg(uid, msg.message_id)
            return

        data["m2"] = m2
        data["price_clean"] = m2 * PRICE_PER_M2

        if data["service"] == "Уборка квартиры":
            data["price"] = data["price_clean"]
            data["step"] = "address"
            msg = await message.answer(f"Стоимость: {data['price']} ₽\nВведите адрес.")
            save_msg(uid, msg.message_id)
            return

        data["step"] = "windows"
        msg = await message.answer("Введите количество окон.")
        save_msg(uid, msg.message_id)
        return

    if step == "windows":
        try:
            w = int(message.text)
            if w <= 0:
                raise ValueError
        except:
            msg = await message.answer("Введите количество окон числом.")
            save_msg(uid, msg.message_id)
            return

        data["windows"] = w
        data["price_windows"] = w * PRICE_PER_WINDOW

        if data["service"] == "Мытьё окон":
            data["price"] = data["price_windows"]
        else:
            data["price"] = data["price_clean"] + data["price_windows"]

        data["step"] = "address"
        msg = await message.answer(f"Стоимость: {data['price']} ₽\nВведите адрес.")
        save_msg(uid, msg.message_id)
        return

    if step == "address":
        data["address"] = message.text
        data["step"] = "time"
        msg = await message.answer("Укажите удобное время.")
        save_msg(uid, msg.message_id)
        return

    if step == "time":
        data["time"] = message.text
        data["step"] = "phone"

        kb = ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="📞 Отправить номер телефона", request_contact=True)]],
            resize_keyboard=True,
            one_time_keyboard=True
        )

        msg = await message.answer(
            "Нажмите кнопку, чтобы отправить номер телефона.",
            reply_markup=kb
        )
        save_msg(uid, msg.message_id)
        return


# ---------------- АДМИН-КНОПКИ ----------------

@dp.callback_query(F.data.startswith("done:"))
async def mark_done(call: types.CallbackQuery):
    order_id = int(call.data.split(":")[1])

    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Нет доступа", show_alert=True)
        return

    order = orders_by_id.get(order_id)
    if not order:
        await call.answer("Заявка не найдена")
        return

    order["status"] = "выполнено"
    await call.message.edit_text(call.message.text + "\n\nСтатус: выполнено")
    await call.answer("Отмечено как выполнено")


@dp.callback_query(F.data.startswith("cancel:"))
async def mark_cancel(call: types.CallbackQuery):
    order_id = int(call.data.split(":")[1])

    if call.from_user.id not in ADMIN_IDS:
        await call.answer("Нет доступа", show_alert=True)
        return

    order = orders_by_id.get(order_id)
    if not order:
        await call.answer("Заявка не найдена")
        return

    order["status"] = "отменено"
    await call.message.edit_text(call.message.text + "\n\nСтатус: отменено")
    await call.answer("Отмечено как отменено")


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


