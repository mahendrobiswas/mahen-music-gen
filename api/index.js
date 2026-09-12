const axios = require('axios');

module.exports = async (req, res) => {
  const YOUR_NAME = "MAHEN";
  
  res.setHeader('Access-Control-Allow-Origin', '*');
  
  const { 
    prompt,
    improve = 'true',
    format = 'wide',
    random = Math.random().toString(36).substring(2, 10),
    download = 'false'
  } = req.query;
  
  if (!prompt) {
    return res.json({
      status: "ACTIVE",
      service: "AI Image Generator",
      developer: YOUR_NAME,
      contact: "@MAHEN",
      endpoints: {
        generate: "/api/image?prompt=YOUR_TEXT",
        example: "/api/image?prompt=sunset%20over%20mountains",
        download: "/api/image?prompt=car&download=true"
      },
      how_to_use: "Send ?prompt=description to generate AI images"
    });
  }
  
  try {
    const imageUrl = `https://img.hazex.workers.dev/?prompt=${encodeURIComponent(prompt)}&improve=${improve}&format=${format}&random=${random}`;
    
    console.log(`Generating: ${prompt}`);
    
    const response = await axios({
      method: 'GET',
      url: imageUrl,
      responseType: 'arraybuffer',
      timeout: 30000
    });
    
    const contentType = response.headers['content-type'] || 'image/jpeg';
    
    if (download === 'true') {
      res.setHeader('Content-Type', contentType);
      res.setHeader('Content-Disposition', `attachment; filename="ai_image_${random}.jpg"`);
      return res.send(response.data);
    }
    
    const base64Image = Buffer.from(response.data).toString('base64');
    
    res.json({
      success: true,
      developer: YOUR_NAME,
      prompt: prompt,
      image_format: format,
      image_size: `${(response.data.length / 1024).toFixed(1)} KB`,
      image_data: `data:${contentType};base64,${base64Image}`,
      download_link: `${req.headers.host}/api/image?prompt=${encodeURIComponent(prompt)}&download=true`
    });
    
  } catch (error) {
    console.error('Error:', error.message);
    
    res.status(500).json({
      success: false,
      developer: YOUR_NAME,
      error: "Could not generate image",
      suggestion: "Try a different description or try again later",
      example: "Use: ?prompt=beautiful landscape"
    });
  }
};
