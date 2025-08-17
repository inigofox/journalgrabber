"""
Zotero API Integration Module using pyzotero
Handles sending articles to Zotero libraries
"""

import os
from pyzotero import zotero
from config import Config

class ZoteroIntegration:
    def __init__(self):
        self.api_key = Config.ZOTERO_API_KEY
        self.user_id = Config.ZOTERO_USER_ID
        self.group_id = Config.ZOTERO_GROUP_ID
        
        # Initialize pyzotero client
        self.zot = None
        if self.is_configured():
            try:
                if self.group_id:
                    # Use group library
                    self.zot = zotero.Zotero(self.group_id, 'group', self.api_key)
                else:
                    # Use user library
                    self.zot = zotero.Zotero(self.user_id, 'user', self.api_key)
            except Exception as e:
                print(f"Warning: Failed to initialize Zotero client: {e}")
    
    def is_configured(self):
        """Check if Zotero integration is properly configured"""
        return bool(self.api_key and self.user_id)
    
    def create_arxiv_item(self, article_data, pdf_path=None):
        """
        Create a Zotero item from arXiv article data using pyzotero
        
        Args:
            article_data: Dictionary containing article metadata
            pdf_path: Optional path to the downloaded PDF
            
        Returns:
            dict: Response from Zotero API or error info
        """
        if not self.is_configured() or not self.zot:
            return {"success": False, "error": "Zotero not configured properly"}
        
        try:
            # Create the item template using pyzotero's item template
            template = self.zot.item_template('preprint')
            
            # Fill in the article data
            template['title'] = article_data.get('title', '')
            template['abstractNote'] = article_data.get('abstract', '')
            template['repository'] = 'arXiv'
            template['archiveID'] = article_data.get('arxiv_id', '')
            template['url'] = f"https://arxiv.org/abs/{article_data.get('arxiv_id', '')}"
            template['date'] = article_data.get('published', '')
            
            # Clear default creators and add authors
            template['creators'] = []
            if 'authors' in article_data and article_data['authors']:
                if isinstance(article_data['authors'], str):
                    authors = [a.strip() for a in article_data['authors'].split(',')]
                else:
                    authors = article_data['authors']
                
                for author in authors:
                    # Split name into first and last
                    name_parts = author.strip().split()
                    if len(name_parts) >= 2:
                        creator = {
                            "creatorType": "author",
                            "firstName": " ".join(name_parts[:-1]),
                            "lastName": name_parts[-1]
                        }
                    else:
                        creator = {
                            "creatorType": "author",
                            "name": author.strip()
                        }
                    template['creators'].append(creator)
            
            # Clear default tags and add subjects
            template['tags'] = []
            if 'subjects' in article_data and article_data['subjects']:
                subjects = article_data['subjects'].split(',') if isinstance(article_data['subjects'], str) else article_data['subjects']
                for subject in subjects:
                    template['tags'].append({"tag": subject.strip()})
            
            print(f"Creating Zotero item: {template['title']}")
            
            # Create the item using pyzotero
            created_items = self.zot.create_items([template])
            
            if created_items['successful']:
                item_key = list(created_items['successful'].keys())[0]
                print(f"Successfully created Zotero item: {item_key}")
                
                # If PDF provided, attach it
                if pdf_path and self._file_exists(pdf_path):
                    attachment_result = self.add_pdf_attachment(item_key, pdf_path)
                    return {
                        "success": True, 
                        "item_key": item_key,
                        "attachment": attachment_result
                    }
                
                return {"success": True, "item_key": item_key}
            else:
                error_details = created_items.get('failed', {})
                return {"success": False, "error": f"Failed to create item: {error_details}"}
                
        except Exception as e:
            return {"success": False, "error": f"Error creating Zotero item: {str(e)}"}
    
    def add_pdf_attachment(self, parent_item_key, pdf_path):
        """
        Add a PDF attachment to an existing Zotero item using pyzotero
        
        Args:
            parent_item_key: The key of the parent item
            pdf_path: Path to the PDF file
            
        Returns:
            dict: Success/error response
        """
        try:
            if not self._file_exists(pdf_path):
                return {"success": False, "error": "PDF file not found"}
            
            print(f"Attaching PDF to Zotero item: {parent_item_key}")
            
            # Get the filename from the path
            filename = os.path.basename(pdf_path)
            
            # Use pyzotero's upload_attachment method for proper file storage
            # This ensures the PDF is stored in Zotero's storage, not just linked
            attachment_info = self.zot.upload_attachment(
                pdf_path,
                parent_item_key,
                filename=filename
            )
            
            if attachment_info:
                print(f"PDF successfully uploaded to Zotero storage")
                return {"success": True, "message": "PDF uploaded and attached successfully"}
            else:
                # Fallback to attachment_simple if upload_attachment fails
                attachment = self.zot.attachment_simple([pdf_path], parent_item_key)
                if attachment:
                    return {"success": True, "message": "PDF attached successfully (linked)"}
                else:
                    return {"success": False, "error": "Failed to attach PDF"}
                
        except Exception as e:
            # If upload_attachment is not available or fails, try attachment_simple
            try:
                print(f"Primary upload failed, trying alternative method: {str(e)}")
                attachment = self.zot.attachment_simple([pdf_path], parent_item_key)
                if attachment:
                    return {"success": True, "message": "PDF attached successfully (alternative method)"}
                else:
                    return {"success": False, "error": "Failed to attach PDF"}
            except Exception as e2:
                return {"success": False, "error": f"PDF attachment failed: {str(e2)}"}
    
    def _file_exists(self, file_path):
        """Check if file exists and is readable"""
        try:
            return os.path.isfile(file_path) and os.access(file_path, os.R_OK)
        except:
            return False
    
    def test_connection(self):
        """Test the Zotero API connection using pyzotero"""
        if not self.is_configured():
            return {"success": False, "error": "API key or user ID not configured"}
        
        if not self.zot:
            return {"success": False, "error": "Zotero client not initialized"}
        
        try:
            # Try to get user/group info to test connection
            if self.group_id:
                # Test group library access
                info = self.zot.group_info()
                library_type = f"group library '{info.get('name', 'Unknown')}'"
            else:
                # Test user library access by getting a few items
                items = self.zot.items(limit=1)
                library_type = "personal library"
            
            return {
                "success": True, 
                "message": f"Zotero connection successful - {library_type}",
                "library_type": "group" if self.group_id else "user"
            }
                
        except Exception as e:
            return {"success": False, "error": f"Connection test failed: {str(e)}"}
    
    def get_user_info(self):
        """Get user information - simplified since pyzotero handles authentication"""
        if not self.is_configured():
            return {"success": False, "error": "API key or user ID not configured"}
        
        try:
            if self.group_id:
                # For group libraries, get group info
                info = self.zot.group_info()
                return {
                    "success": True,
                    "user_id": self.user_id,
                    "group_id": self.group_id,
                    "group_name": info.get('name', 'Unknown'),
                    "library_type": "group"
                }
            else:
                # For user libraries, just return the configured user ID
                return {
                    "success": True,
                    "user_id": self.user_id,
                    "library_type": "user"
                }
                
        except Exception as e:
            return {"success": False, "error": f"Failed to get user info: {str(e)}"}
