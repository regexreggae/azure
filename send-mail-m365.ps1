function Send-O365EmailGraphApi($MailSender, $SendAs, $MailReceiver, $MailSubject, $MailBody, $MailAttachmentTextFile) {
  #sends a simple html-mail from sender to receiver using an Azure App with send-mail permissions (which in turn uses the Graph API)
  #call like this: Send-O365EmailGraphApi -MailSubject "Test" -MailBody "<h1>Hello World</h1><p>sent thru Graph API</p> etc.
  #if attachment is desired, specify path as string, like so: -$MailAttachmentTextFile "C:\temp\test.txt"
  #only $MailSubject and $MailBody are required values, everything else is optional
  
  #default values if not specified by user
  if (! ($MailSender)) { $MailSender = "default-sender@yourcompany.org" }
  if (! ($MailReceiver)) { $MailReceiver = "default-receiver@yourcompany.org" }
  if (! ($SendAs)) {
    if ( $MailSender -eq "default-sender@yourcompany.org") { $SendAs = "default-send-as@yourcompany.org" } else { $SendAs = $MailSender }
  }
 
  #required values for using . These are fetched from environment variables here
  $clientID = $env:m365_client_id
  $Clientsecret = $env:m365_client_secret
  $tenantID = $env:m365_tenant_id

  #Connect to GRAPH API to get a token. The token is your ticket for sending the email later (= authorization)
  $tokenBody = @{
      Grant_Type    = "client_credentials"
      Scope         = "https://graph.microsoft.com/.default"
      Client_Id     = $clientId
      Client_Secret = $clientSecret
  }
  $tokenResponse = Invoke-RestMethod -Uri "https://login.microsoftonline.com/$tenantID/oauth2/v2.0/token" -Method POST -Body $tokenBody
  $headers = @{
      "Authorization" = "Bearer $($tokenResponse.access_token)"
      "Content-type"  = "application/json"
  }

  #Define URL and body for the intended request
  $URLsend = "https://graph.microsoft.com/v1.0/users/$MailSender/sendMail"
  $body_json_hashtable = @{
    message = @{
        subject = "$MailSubject"
        body = @{
            contentType = "HTML"
            content = "$MailBody"
        }
        toRecipients = @(
            @{
                emailAddress = @{
                    address = "$MailReceiver"
                }
            }
        )
        sender = @{
            emailAddress = @{
                address = "$MailSender"
            }
        }
        from = @{
            emailAddress = @{
                address = "$SendAs"
            }
        }
    }
    saveToSentItems = "false"
  }

  #### Add Attachment: only if there is one specified!
  if ($MailAttachmentTextFile) {
    #Add the attachment information to the $BodyJsonsend variable
    #Convert To Base64
    $readableText = Get-Content -Path $MailAttachmentTextFile -Raw
    $encodedBytes = [System.Text.Encoding]::UTF8.GetBytes($readableText)
    $encodedText = [System.Convert]::ToBase64String($encodedBytes)
    #specify file name
    $MailAttachmentTextFileName = [System.IO.Path]::GetFileName($MailAttachmentTextFile)
    #create key etc.
    $body_json_hashtable["message"].Add("attachments", @(@{}))
    #fill the attachment values
    $body_json_hashtable["message"]["attachments"][0]["@odata.type"] = "#microsoft.graph.fileAttachment"
    $body_json_hashtable["message"]["attachments"][0]["name"] = "$MailAttachmentTextFileName"
    $body_json_hashtable["message"]["attachments"][0]["contentType"] = "application/octet-stream"
    $body_json_hashtable["message"]["attachments"][0]["contentBytes"] = "$encodedText"
  }

  #convert email body to json
  $body_json_hashtable = $body_json_hashtable | ConvertTo-Json -Depth 4

  #Send Mail and store response to variable
  try {
    $MailSendRequestResponse = Invoke-WebRequest -Method POST -Uri $URLsend -Headers $headers -Body $body_json_hashtable
    return $MailSendRequestResponse.StatusCode
  } catch {
    #Return 400 as generic error status code
    return 400
  }
  
}