from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageOps, ImageFilter, ImageChops, ImageEnhance
import numpy as np
import io
import json
import os
from datetime import datetime

# Get sensitive data from environment variables
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))

# File to store user data
USER_DB_FILE = "users.json"

# Initialize user database
def load_users():
    if os.path.exists(USER_DB_FILE):
        with open(USER_DB_FILE, 'r') as f:
            return json.load(f)
    return {"users": {}, "total_images": 0}

def save_users(data):
    with open(USER_DB_FILE, 'w') as f:
        json.dump(data, f, indent=2)

user_data = load_users()

# Track user activity
def track_user(user_id, username):
    user_id_str = str(user_id)
    if user_id_str not in user_data["users"]:
        user_data["users"][user_id_str] = {
            "username": username,
            "first_seen": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "images_processed": 0
        }
    else:
        user_data["users"][user_id_str]["last_active"] = datetime.now().isoformat()
        user_data["users"][user_id_str]["username"] = username
    save_users(user_data)

def increment_image_count(user_id):
    user_id_str = str(user_id)
    user_data["users"][user_id_str]["images_processed"] += 1
    user_data["total_images"] += 1
    save_users(user_data)

# Improved sketch functions
def dodge(front, back):
    result = front * 255 / (255 - back + 1)  # Added +1 to prevent division by zero
    result[result > 255] = 255
    result[back == 255] = 255
    return result.astype('uint8')

def enhance_edges(image):
    edges = image.filter(ImageFilter.FIND_EDGES)
    edges = ImageOps.invert(edges)
    return edges

def pencil_sketch(image):
    """
    Improved sketch with smoother results
    """
    try:
        # Convert the image to grayscale
        gray_image = ImageOps.grayscale(image)
        
        # Enhance contrast slightly for better results
        enhancer = ImageEnhance.Contrast(gray_image)
        gray_image = enhancer.enhance(1.2)
        
        # Invert the grayscale image
        inverted_image = ImageOps.invert(gray_image)
        
        # Blur the inverted image (increased blur for smoother effect)
        blurred_image = inverted_image.filter(ImageFilter.GaussianBlur(15))
        
        # Convert images to numpy arrays for manipulation
        gray_array = np.asarray(gray_image).astype('float64')
        blurred_array = np.asarray(blurred_image).astype('float64')
        
        # Apply the custom dodge function
        result_array = dodge(gray_array, blurred_array)
        
        # Convert the result array back to an image
        pencil_sketch_image = Image.fromarray(result_array)
        
        # Enhance the edges with smoother filter
        edges = enhance_edges(gray_image)
        edges = edges.filter(ImageFilter.SMOOTH_MORE)
        
        # Blend the pencil sketch image with the edges
        pencil_sketch_image = ImageChops.multiply(pencil_sketch_image, edges)
        
        # Final smoothing pass
        pencil_sketch_image = pencil_sketch_image.filter(ImageFilter.SMOOTH)
        
        return pencil_sketch_image
    
    except Exception as e:
        print(f"Error in pencil_sketch: {e}")
        return None

# Bot command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    user = update.effective_user
    track_user(user.id, user.username or user.first_name)
    
    await update.message.reply_text(
        f"👋 Hello {user.first_name}! I'm the Sketch Master Bot!\n\n"
        "📸 Send me any photo and I'll convert it to a beautiful pencil sketch!\n\n"
        "Commands:\n"
        "/help - Show help\n"
        "/myid - Get your Telegram ID\n\n"
        "Made by Ramsfield 🎨"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "📖 How to use:\n\n"
        "1. Send me any photo (NOT as document)\n"
        "2. Wait a few seconds while I process it\n"
        "3. Receive your sketched image!\n\n"
        "💡 Tips:\n"
        "- Send photos as 'Photo', not 'File'\n"
        "- Clear photos work best\n"
        "- Processing takes 5-10 seconds\n\n"
        "That's it! Simple and free! 🎨"
    )

async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show user their Telegram ID."""
    user_id = update.effective_user.id
    await update.message.reply_text(f"🆔 Your Telegram ID: `{user_id}`", parse_mode='Markdown')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to view statistics."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only for the admin.")
        return
    
    total_users = len(user_data["users"])
    total_images = user_data["total_images"]
    
    # Get active users (last 7 days)
    from datetime import datetime, timedelta
    week_ago = datetime.now() - timedelta(days=7)
    active_users = sum(
        1 for u in user_data["users"].values()
        if datetime.fromisoformat(u["last_active"]) > week_ago
    )
    
    stats_text = (
        "📊 **Bot Statistics**\n\n"
        f"👥 Total Users: {total_users}\n"
        f"🔥 Active Users (7d): {active_users}\n"
        f"🖼 Total Images Processed: {total_images}\n"
        f"📈 Avg Images/User: {total_images/total_users if total_users > 0 else 0:.1f}\n"
    )
    
    await update.message.reply_text(stats_text, parse_mode='Markdown')

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to broadcast message to all users."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ This command is only for the admin.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📢 **Broadcast Usage:**\n\n"
            "`/broadcast Your message here`\n\n"
            "This will send the message to all bot users.",
            parse_mode='Markdown'
        )
        return
    
    message = ' '.join(context.args)
    total_users = len(user_data["users"])
    success_count = 0
    fail_count = 0
    
    status_msg = await update.message.reply_text(
        f"📤 Broadcasting to {total_users} users...\n\n"
        "⏳ Please wait..."
    )
    
    for user_id in user_data["users"].keys():
        try:
            await context.bot.send_message(
                chat_id=int(user_id),
                text=f"📢 **Message from Admin:**\n\n{message}",
                parse_mode='Markdown'
            )
            success_count += 1
        except Exception as e:
            fail_count += 1
            print(f"Failed to send to {user_id}: {e}")
    
    await status_msg.edit_text(
        f"✅ Broadcast Complete!\n\n"
        f"✓ Sent: {success_count}\n"
        f"✗ Failed: {fail_count}\n"
        f"📊 Total: {total_users}"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photos sent by users."""
    try:
        user = update.effective_user
        track_user(user.id, user.username or user.first_name)
        
        # Send processing message
        processing_msg = await update.message.reply_text(
            "⏳ Processing your image...\n"
            "This may take 5-10 seconds. Please wait! 🎨"
        )
        
        # Get the photo
        photo = await update.message.photo[-1].get_file()
        
        # Download photo to memory
        photo_bytes = await photo.download_as_bytearray()
        
        # Open image with PIL
        image = Image.open(io.BytesIO(photo_bytes))
        
        # Apply improved sketch effect
        sketch_image = pencil_sketch(image)
        
        if sketch_image is None:
            await processing_msg.edit_text(
                "❌ Sorry, there was an error processing your image.\n"
                "Please try again with a different photo!"
            )
            return
        
        # Save sketch to memory
        output_buffer = io.BytesIO()
        sketch_image.save(output_buffer, format='JPEG', quality=95)
        output_buffer.seek(0)
        
        # Send the sketched image back
        await update.message.reply_photo(
            photo=output_buffer,
            caption=(
                "✨ Here's your enhanced pencil sketch!\n\n"
                "🎨 Made by Sketch Master Bot\n"
                "💡 Send another photo to try again!"
            )
        )
        
        # Delete processing message
        await processing_msg.delete()
        
        # Increment image counter
        increment_image_count(user.id)
        
    except Exception as e:
        print(f"Error handling photo: {e}")
        await update.message.reply_text(
            "❌ Oops! Something went wrong.\n"
            "Please try sending the image again!\n\n"
            "💡 Make sure to send as 'Photo', not 'File'"
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle images sent as documents - reject them."""
    await update.message.reply_text(
        "❌ **Invalid File Type!**\n\n"
        "Please send your image as a **Photo**, not as a **Document/File**!\n\n"
        "📱 How to send as photo:\n"
        "1. Tap the 📎 attachment icon\n"
        "2. Select 'Gallery' or 'Camera'\n"
        "3. Choose your image\n"
        "4. Make sure it's sent as a photo, not a file!\n\n"
        "Try again! 📸",
        parse_mode='Markdown'
    )

async def handle_other_files(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle other file types - reject them."""
    await update.message.reply_text(
        "❌ **Invalid File Type!**\n\n"
        "I can only process **photos/images**.\n\n"
        "Please send:\n"
        "✅ Photos (JPG, PNG)\n"
        "❌ NOT videos, documents, or other files\n\n"
        "Send a photo and try again! 📸"
    )

def main():
    """Start the bot."""
    # Get token from environment variable
    TOKEN = os.environ.get('BOT_TOKEN')
    
    if not TOKEN:
        print("❌ ERROR: BOT_TOKEN environment variable not set!")
        print("Please set BOT_TOKEN in your hosting platform's environment variables.")
        exit(1)
    
    if ADMIN_ID == 0:
        print("⚠️ WARNING: ADMIN_ID not set. Admin commands will not work.")
    
    # Create the Application with increased timeout
    from telegram.request import HTTPXRequest
    request = HTTPXRequest(
        connection_pool_size=8,
        connect_timeout=30.0,
        read_timeout=30.0,
        write_timeout=30.0,
        pool_timeout=30.0
    )
    
    application = Application.builder().token(TOKEN).request(request).build()
    
    # Register command handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("myid", myid_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # Register photo handler
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Register document handler (reject images sent as documents)
    application.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    
    # Register other file type handlers (reject videos, audio, etc)
    application.add_handler(MessageHandler(
        filters.Document.ALL | filters.VIDEO | filters.AUDIO | filters.VOICE,
        handle_other_files
    ))
    
    # Start the bot
    print("🤖 Sketch Master Bot is running!")
    print(f"👤 Admin ID: {ADMIN_ID}")
    print("Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()