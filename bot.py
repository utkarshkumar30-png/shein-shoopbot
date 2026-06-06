import telebot
from telebot import types
import os
import json
import uuid
import time

# =========================
# CONFIG
# =========================
BOT_TOKEN = "8115455351:AAGFgcMirYUIqC5l_YKyuEFcOmI6A-wUIIA"
OWNER_ID = 1841699773   # your Telegram numeric ID
NORMAL_PRICE_PER_CODE = 190
BULK_PRICE_PER_CODE = 150
BULK_MIN_QTY = 10
UPI_ID = "9296532474@pthdfc"
ADMIN_USERNAME = "@your_username"   # optional
QR_IMAGE = "qr.jpg.jpg"   # keep your QR image in same folder with this name

COUPONS_FILE = "coupons.txt"
SOLD_FILE = "sold.txt"
PENDING_FILE = "pending_orders.json"

bot = telebot.TeleBot(BOT_TOKEN)

# Users waiting to type custom quantity
waiting_custom_qty = set()

def calculate_price(qty):
    if qty >= BULK_MIN_QTY:
        return BULK_PRICE_PER_CODE
    return NORMAL_PRICE_PER_CODE

# =========================
# FILE HELPERS
# =========================
def load_coupons():
    if not os.path.exists(COUPONS_FILE):
        return []
    with open(COUPONS_FILE, "r", encoding="utf-8") as f:
        return [line.strip() for line in f if line.strip()]


def save_coupons(coupons):
    with open(COUPONS_FILE, "w", encoding="utf-8") as f:
        for c in coupons:
            f.write(c + "\n")


def load_pending_orders():
    if not os.path.exists(PENDING_FILE):
        return {}
    with open(PENDING_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return {}


def save_pending_orders(data):
    with open(PENDING_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save_sold_coupon(order_id, user_id, username, coupon):
    with open(SOLD_FILE, "a", encoding="utf-8") as f:
        f.write(
            f"Order: {order_id} | User ID: {user_id} | Username: @{username} | Coupon: {coupon}\n"
        )


# =========================
# ORDER HELPERS
# =========================
def create_order(user, qty):
    coupons = load_coupons()
    available_stock = len(coupons)

    if qty > available_stock:
        return None

    price_per_code = calculate_price(qty)
    total_amount = qty * price_per_code

    orders = load_pending_orders()
    order_id = "ORD-" + uuid.uuid4().hex[:8].upper()

    orders[order_id] = {
        "user_id": user.id,
        "username": user.username if user.username else "no_username",
        "first_name": user.first_name if user.first_name else "",
        "qty": qty,
        "price_per_code": price_per_code,
        "amount": total_amount,
        "status": "awaiting_payment",
        "created_at": int(time.time())
    }

    save_pending_orders(orders)
    return order_id

def get_latest_unpaid_order(user_id):
    orders = load_pending_orders()
    user_orders = []

    for order_id, order in orders.items():
        if order["user_id"] == user_id and order["status"] == "awaiting_payment":
            user_orders.append((order_id, order))

    if not user_orders:
        return None

    # latest order
    user_orders.sort(key=lambda x: x[1].get("created_at", 0), reverse=True)
    return user_orders[0][0]


def send_payment_details(chat_id, order_id):
    orders = load_pending_orders()
    order = orders[order_id]

    text = (
        f"🛍 Order ID: {order_id}\n"
        f"📦 Number of codes: {order['qty']}\n"
        f"🏷 Price per code: ₹{order['price_per_code']}\n"
        f"💰 Total amount: ₹{order['amount']}\n"
        f"🏦 UPI ID: {UPI_ID}\n\n"
        f"Please pay the amount and send payment screenshot here.\n"
        f"After admin verifies, you will receive your coupon code(s)."
    )

    if os.path.exists(QR_IMAGE):
        with open(QR_IMAGE, "rb") as photo:
            bot.send_photo(chat_id, photo, caption=text)
    else:
        bot.send_message(chat_id, text)


def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("Buy Coupon", "Available Stock")
    markup.add("Contact Admin")
    return markup


def qty_inline_keyboard():
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton("1 Code", callback_data="qty_1"),
        types.InlineKeyboardButton("2 Codes", callback_data="qty_2")
    )
    markup.row(
        types.InlineKeyboardButton("5 Codes", callback_data="qty_5"),
        types.InlineKeyboardButton("Custom", callback_data="qty_custom")
    )
    return markup


# =========================
# START
# =========================
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "Welcome 👋\nChoose an option below.",
        reply_markup=main_menu()
    )


# =========================
# BUTTON HANDLERS
# =========================
@bot.message_handler(func=lambda m: m.text == "Buy Coupon")
def buy_coupon(message):
    bot.send_message(
        message.chat.id,
        "How many coupon codes do you want?",
        reply_markup=qty_inline_keyboard()
    )


@bot.message_handler(func=lambda m: m.text == "Available Stock")
def available_stock(message):
    coupons = load_coupons()
    bot.send_message(message.chat.id, f"Available coupon codes: {len(coupons)}")


@bot.message_handler(func=lambda m: m.text == "Contact Admin")
def contact_admin(message):
    bot.send_message(message.chat.id, f"For help, contact: {ADMIN_USERNAME}")


# =========================
# INLINE BUTTONS
# =========================
@bot.callback_query_handler(func=lambda call: call.data.startswith("qty_"))
def handle_qty_selection(call):
    user = call.from_user

    if call.data == "qty_custom":
        waiting_custom_qty.add(user.id)
        bot.send_message(call.message.chat.id, "Please type how many codes you want (example: 3)")
        return

    qty = int(call.data.split("_")[1])

    if qty <= 0:
        bot.send_message(call.message.chat.id, "Invalid quantity.")
        return

    order_id = create_order(user, qty)

    if order_id is None:
        available_stock = len(load_coupons())
        bot.send_message(
            call.message.chat.id,
            f"Out of stock ❌\n\n"
            f"Available codes: {available_stock}\n"
            f"You requested: {qty}\n\n"
            f"Please choose a lower quantity."
        )
        return

    send_payment_details(call.message.chat.id, order_id)

# =========================
# CUSTOM QUANTITY INPUT
# =========================
@bot.message_handler(func=lambda m: m.from_user.id in waiting_custom_qty)
def handle_custom_qty(message):
    user_id = message.from_user.id

    try:
        qty = int(message.text.strip())
        if qty <= 0:
            bot.send_message(message.chat.id, "Please enter a valid number greater than 0.")
            return
    except:
        bot.send_message(message.chat.id, "Please send only a number. Example: 3")
        return

    waiting_custom_qty.discard(user_id)

    order_id = create_order(message.from_user, qty)

    if order_id is None:
        available_stock = len(load_coupons())
        bot.send_message(
            message.chat.id,
            f"Out of stock ❌\n\n"
            f"Available codes: {available_stock}\n"
            f"You requested: {qty}\n\n"
            f"Please choose a lower quantity."
        )
        return

    send_payment_details(message.chat.id, order_id)


# =========================
# PAYMENT SCREENSHOT
# =========================
@bot.message_handler(content_types=["photo"])
def handle_payment_screenshot(message):
    user = message.from_user
    order_id = get_latest_unpaid_order(user.id)

    if not order_id:
        bot.send_message(
            message.chat.id,
            "No pending order found.\nPlease click 'Buy Coupon' first."
        )
        return

    orders = load_pending_orders()
    orders[order_id]["status"] = "payment_sent"
    save_pending_orders(orders)

    bot.send_message(
        message.chat.id,
        f"Payment screenshot received ✅\nYour order ID: {order_id}\nPlease wait for admin verification."
    )

    # forward screenshot to admin
    bot.forward_message(OWNER_ID, message.chat.id, message.message_id)

    admin_text = (
        f"📥 New payment screenshot received\n\n"
        f"Order ID: {order_id}\n"
        f"User ID: {user.id}\n"
        f"Username: @{user.username if user.username else 'no_username'}\n"
        f"Codes requested: {orders[order_id]['qty']}\n"
        f"Amount: ₹{orders[order_id]['amount']}\n\n"
        f"To approve, send:\n"
        f"/approve {order_id}\n\n"
        f"To reject, send:\n"
        f"/reject {order_id}"
    )

    bot.send_message(OWNER_ID, admin_text)


# =========================
# APPROVE ORDER
# =========================
@bot.message_handler(commands=["approve"])
def approve_order(message):
    if message.from_user.id != OWNER_ID:
        bot.send_message(message.chat.id, "You are not authorized.")
        return

    parts = message.text.split()

    if len(parts) != 2:
        bot.send_message(message.chat.id, "Use format: /approve ORDER_ID")
        return

    order_id = parts[1].strip()
    orders = load_pending_orders()

    if order_id not in orders:
        bot.send_message(message.chat.id, "Order not found.")
        return

    order = orders[order_id]

    if order["status"] == "completed":
        bot.send_message(message.chat.id, "This order is already completed.")
        return

    if order["status"] == "rejected":
        bot.send_message(message.chat.id, "This order is already rejected.")
        return

    qty = order["qty"]
    coupons = load_coupons()

    if len(coupons) < qty:
        bot.send_message(
            message.chat.id,
            f"Not enough coupons left.\nRequired: {qty}\nAvailable: {len(coupons)}"
        )
        return

    selected_codes = coupons[:qty]
    remaining_codes = coupons[qty:]
    save_coupons(remaining_codes)

    # save sold log
    for code in selected_codes:
        save_sold_coupon(order_id, order["user_id"], order["username"], code)

    order["status"] = "completed"
    order["codes_sent"] = selected_codes
    save_pending_orders(orders)

    code_text = "\n".join([f"{i+1}. {code}" for i, code in enumerate(selected_codes)])

    customer_message = (
        f"✅ Payment verified!\n\n"
        f"Order ID: {order_id}\n"
        f"You purchased {qty} coupon code(s).\n\n"
        f"Here are your code(s):\n{code_text}\n\n"
        f"Thank you for your purchase."
    )

    bot.send_message(order["user_id"], customer_message)
    bot.send_message(message.chat.id, f"Approved successfully ✅\nCodes sent for {order_id}")


# =========================
# REJECT ORDER
# =========================
@bot.message_handler(commands=["reject"])
def reject_order(message):
    if message.from_user.id != OWNER_ID:
        bot.send_message(message.chat.id, "You are not authorized.")
        return

    parts = message.text.split()

    if len(parts) != 2:
        bot.send_message(message.chat.id, "Use format: /reject ORDER_ID")
        return

    order_id = parts[1].strip()
    orders = load_pending_orders()

    if order_id not in orders:
        bot.send_message(message.chat.id, "Order not found.")
        return

    orders[order_id]["status"] = "rejected"
    save_pending_orders(orders)

    bot.send_message(
        orders[order_id]["user_id"],
        f"❌ Your payment/order for {order_id} was not approved.\nPlease contact admin: {ADMIN_USERNAME}"
    )

    bot.send_message(message.chat.id, f"Order {order_id} rejected.")


# =========================
# ADMIN STOCK
# =========================
@bot.message_handler(commands=["stock"])
def stock_command(message):
    if message.from_user.id != OWNER_ID:
        return

    coupons = load_coupons()
    bot.send_message(message.chat.id, f"Remaining coupons: {len(coupons)}")


print("Bot is running...")
bot.infinity_polling()