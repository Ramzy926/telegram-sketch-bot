from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from PIL import Image, ImageOps, ImageFilter, ImageChops
import numpy as np
import io
import os

# Your existing sketch functions
def dodge(front, back):
    result = front * 255 / (255 - back)
    result[result > 255] = 255
    result[back == 255] = 255
    return result.astype('uint8')

def enhance_edges(image):
    edges = image.filter(ImageFilter.FIND_EDGES)
    edges = ImageOps.invert(edges)
    return edges

def pencil_sketch(image):
    """
    Converts an image to pencil sketch
    Takes PIL Image object, returns PIL Image object
    """
    try:
        # Convert the image to grayscale
        gray_image = ImageOps.grayscale(image)
        
        # Invert the grayscale image
        inverted_image = ImageOps.invert(gray_image)
        
        # Blur the inverted image
        blurred_image = inverted_image.filter(ImageFilter.GaussianBlur(10))
        
        # Convert images to numpy arrays for manipulation
        gray_array = np.asarray(gray_image).astype('float64')
        blurred_array = np.asarray(blurred_image).astype('float64')
        
        # Apply the custom dodge function
        result_array = dodge(gray_array, blurred_array)
        
        # Convert the result array back to an image
        pencil_sketch_image = Image.fromarray(result_array)
        
        # Enhance the edges
        edges = enhance_edges(gray_image)
        
        # Blend the pencil sketch image with the edges
        pencil_sketch_image = ImageChops.multiply(pencil_sketch_image, edges)
        
        return pencil_sketch_image
    
    except Exception as e:
        print(f"Error in pencil_sketch: {e}")
        return None

# Bot command handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /start is issued."""
    await update.message.reply_text(
        "👋 Hello! I'm the Sketch Master Bot!\n\n"
        "📸 Send me any photo and I'll convert it to a beautiful pencil sketch!\n\n"
        "Made by Ramsfield 🎨"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send a message when the command /help is issued."""
    await update.message.reply_text(
        "📖 How to use:\n\n"
        "1. Send me any photo\n"
        "2. Wait a few seconds while I process it\n"
        "3. Receive your sketched image!\n\n"
        "That's it! Simple and free! 🎨"
    )

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle photos sent by users."""
    try:
        # Send processing message
        processing_msg = await update.message.reply_text("⏳ Processing your image... Please wait!")
        
        # Get the photo
        photo = await update.message.photo[-1].get_file()
        
        # Download photo to memory
        photo_bytes = await photo.download_as_bytearray()
        
        # Open image with PIL
        image = Image.open(io.BytesIO(photo_bytes))
        
        # Apply sketch effect
        sketch_image = pencil_sketch(image)
        
        if sketch_image is None:
            await processing_msg.edit_text("❌ Sorry, there was an error processing your image. Please try again!")
            return
        
        # Save sketch to memory
        output_buffer = io.BytesIO()
        sketch_image.save(output_buffer, format='JPEG')
        output_buffer.seek(0)
        
        # Send the sketched image back
        await update.message.reply_photo(
            photo=output_buffer,
            caption="✨ Here's your pencil sketch! Made by Sketch Master Bot 🎨"
        )
        
        # Delete processing message
        await processing_msg.delete()
        
    except Exception as e:
        print(f"Error handling photo: {e}")
        await update.message.reply_text(
            "❌ Oops! Something went wrong. Please try sending the image again!"
        )

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle images sent as documents."""
    await update.message.reply_text(
        "📎 Please send your image as a photo, not as a document!\n\n"
        "Tip: In Telegram, when sending an image, make sure to tap 'Send as Photo' not 'Send as File'."
    )

def main():
    """Start the bot."""
    # Replace with your bot token
    TOKEN = "8338505230:AAGKRnZSPLKNlIqjPA2FQRumLS-8WR2p2jA"
    
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
    
    # Register photo handler
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    # Register document handler (to tell users to send as photo)
    application.add_handler(MessageHandler(filters.Document.IMAGE, handle_document))
    
    # Start the bot
    print("🤖 Bot is running! Press Ctrl+C to stop.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()