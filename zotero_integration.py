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
                # Fix: Get the actual item key from the response
                item_info = created_items['successful']['0']  # The key '0' is the index, not the item key
                item_key = item_info['key']  # Get the actual Zotero item key
                print(f"Successfully created Zotero item with key: {item_key}")
                
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
            print(f"PDF path: {pdf_path}")
            print(f"PDF file size: {os.path.getsize(pdf_path)} bytes")
            
            # Get the file info
            filename = os.path.basename(pdf_path)
            filesize = os.path.getsize(pdf_path)
            
            # First attempt: Use attachment_simple which is the standard pyzotero method
            try:
                print(f"Attempting attachment_simple with file: {filename}")
                # attachment_simple in pyzotero expects a list of paths and the parent item key
                result = self.zot.attachment_simple([pdf_path], parent_item_key)
                
                if result:
                    print(f"PDF successfully attached via attachment_simple")
                    return {"success": True, "message": "PDF attached successfully"}
                else:
                    print("attachment_simple returned False/None")
                    
            except Exception as e:
                print(f"attachment_simple failed: {e}")
            
            # Second attempt: Try upload_attachment if available (newer pyzotero versions)
            try:
                print("Attempting upload_attachment method...")
                # Some versions of pyzotero have this method
                result = self.zot.upload_attachment(pdf_path, parent_item_key)
                
                if result:
                    print(f"PDF successfully uploaded via upload_attachment")
                    return {"success": True, "message": "PDF uploaded successfully"}
                    
            except (AttributeError, TypeError) as e:
                print(f"upload_attachment not available or failed: {e}")
            
            # Third attempt: Manual file upload with proper attachment creation
            try:
                print("Attempting manual file upload...")
                
                # Step 1: Create attachment item with proper linkMode
                attachment_template = self.zot.item_template('attachment')
                attachment_template['parentItem'] = parent_item_key
                attachment_template['linkMode'] = 'imported_file'
                attachment_template['title'] = filename
                attachment_template['filename'] = filename
                attachment_template['contentType'] = 'application/pdf'
                
                print(f"Creating attachment item for: {filename}")
                created = self.zot.create_items([attachment_template])
                
                if created and created.get('successful'):
                    # Get the attachment key - handle different response formats
                    if '0' in created['successful']:
                        attachment_info = created['successful']['0']
                    else:
                        # Get the first item if indexed differently
                        first_key = list(created['successful'].keys())[0]
                        attachment_info = created['successful'][first_key]
                    
                    attachment_key = attachment_info.get('key') or attachment_info.get('data', {}).get('key')
                    
                    if not attachment_key:
                        print(f"Could not extract attachment key from response: {attachment_info}")
                        return {"success": False, "error": "Failed to get attachment key"}
                    
                    print(f"Attachment item created with key: {attachment_key}")
                    
                    # Step 2: Try to upload the actual file using different methods
                    try:
                        # Method 1: file_upload_auth + upload_file (if available)
                        print("Trying file_upload_auth method...")
                        upload_auth = self.zot.file_upload_auth(
                            attachment_key,
                            filename=filename,
                            filesize=filesize,
                            mtime=int(os.path.getmtime(pdf_path))
                        )
                        
                        if upload_auth:
                            with open(pdf_path, 'rb') as f:
                                upload_result = self.zot.upload_file(f, upload_auth)
                            
                            if upload_result:
                                print("PDF file uploaded successfully via file_upload_auth")
                                return {"success": True, "message": "PDF uploaded successfully"}
                    except (AttributeError, KeyError) as auth_error:
                        print(f"file_upload_auth method not available: {auth_error}")
                    
                    # Method 2: Direct attachment upload (fallback)
                    try:
                        print("Trying direct attachment upload...")
                        with open(pdf_path, 'rb') as f:
                            result = self.zot.upload_attachment(f, attachment_key)
                        if result:
                            print("PDF uploaded via direct attachment upload")
                            return {"success": True, "message": "PDF uploaded successfully"}
                    except Exception as direct_error:
                        print(f"Direct upload failed: {direct_error}")
                    
                    # If we created the attachment but couldn't upload the file
                    print("Warning: Attachment metadata created but file upload failed")
                    return {"success": True, "message": "Attachment created (metadata only, file upload failed)"}
                else:
                    print(f"Failed to create attachment item: {created}")
                    return {"success": False, "error": "Failed to create attachment item"}
                    
            except Exception as e:
                print(f"Manual upload failed with error: {e}")
                import traceback
                traceback.print_exc()
                return {"success": False, "error": f"PDF attachment failed: {str(e)}"}
                
        except Exception as e:
            print(f"Unexpected error during PDF attachment: {str(e)}")
            import traceback
            traceback.print_exc()
            return {"success": False, "error": f"PDF attachment failed: {str(e)}"}
    
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
            #
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
